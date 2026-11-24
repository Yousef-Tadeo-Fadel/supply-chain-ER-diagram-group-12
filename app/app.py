import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import psycopg
from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from psycopg import sql
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from workflows import InvalidWorkflow, prepare, confirm, lock_order

from catalog import TABLES, OPTIONS, REFERENCES, LIMITS, field_type, required
from credentials import matches
from db import connect


app = Flask(__name__)
production = os.getenv("APP_MODE", "demo") == "production"
demo_file = Path(__file__).with_name("demo-accounts.json")
demo = json.loads(demo_file.read_text())
accounts = json.loads(Path(os.environ["ACCOUNT_FILE"]).read_text()) if production else demo
if production:
    if len(os.getenv("SESSION_SECRET", "")) < 48:
        raise RuntimeError("Configure the production session secret.")
    if any(matches(pw, record["hash"]) for record in accounts.values()
           for pw in ("Classroom-Admin-12", "Classroom-Reader-12")):
        raise RuntimeError("Production requires private credentials.")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
app.config.update(SECRET_KEY=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=production, PERMANENT_SESSION_LIFETIME=timedelta(hours=4),
                  SESSION_REFRESH_EACH_REQUEST=False, MAX_CONTENT_LENGTH=32 * 1024)
AUTH_DB = os.getenv("AUTH_STATE", "/tmp/cmpe341-auth.sqlite")
with closing(sqlite3.connect(AUTH_DB)) as state:
    state.execute("CREATE TABLE IF NOT EXISTS attempts (client TEXT PRIMARY KEY, started INTEGER, n INTEGER)")
    state.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, username TEXT, expires INTEGER)")


def allow_attempt(client):
    now = int(time.time())
    with closing(sqlite3.connect(AUTH_DB)) as state, state:
        state.execute("DELETE FROM attempts WHERE started <= ?", (now - 300,))
        state.execute("INSERT INTO attempts VALUES (?, ?, 1) ON CONFLICT(client) DO UPDATE SET n=n+1",
                      (client, now))
        return state.execute("SELECT n FROM attempts WHERE client=?", (client,)).fetchone()[0] <= 10


def token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


app.jinja_env.globals.update(tables=TABLES, csrf_token=token, field_type=field_type,
                             required=required, limits=LIMITS)


@app.before_request
def authenticate():
    g.user = None
    g.role = None
    if request.endpoint in ("static", "health") or request.endpoint is None:
        return
    if request.method == "POST":
        submitted = request.form.get("csrf", "")
        expected = session.get("csrf", "")
        if not expected or not hmac.compare_digest(submitted.encode(), expected.encode()):
            abort(400, "The form expired. Reload the page and try again.")
    if "sid" in session:
        with closing(sqlite3.connect(AUTH_DB)) as state:
            row = state.execute("SELECT username FROM sessions WHERE id=? AND expires>?",
                                (session["sid"], int(time.time()))).fetchone()
        if row and row[0] in accounts:
            g.user = row[0]
            g.role = accounts[g.user]["role"]
    if not g.user and request.endpoint != "login":
        return redirect(url_for("login"))


@app.after_request
def headers(response):
    response.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
                             "Content-Security-Policy": "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                             "Cache-Control": "no-store"})
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if not allow_attempt(request.remote_addr or "unknown"):
            abort(429, "Too many sign-in attempts. Try again in five minutes.")
        name = request.form.get("username", "").strip()
        record = accounts.get(name)
        # Check a real hash on unknown users as well.
        correct = matches(request.form.get("password", ""), (record or next(iter(accounts.values())))["hash"])
        if record and correct:
            session.clear()
            session.permanent = True
            session["sid"] = secrets.token_urlsafe(32)
            now = int(time.time())
            with closing(sqlite3.connect(AUTH_DB)) as state, state:
                state.execute("DELETE FROM sessions WHERE expires<=?", (now,))
                state.execute("INSERT INTO sessions VALUES (?, ?, ?)", (session["sid"], name, now + 14400))
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Incorrect username or password."), 401
    return render_template("login.html")


@app.post("/logout")
def logout():
    with closing(sqlite3.connect(AUTH_DB)) as state, state:
        state.execute("DELETE FROM sessions WHERE id=?", (session.get("sid"),))
    session.clear()
    return redirect(url_for("login"))


@app.get("/health")
def health():
    try:
        with connect() as db:
            db.execute("SELECT 1 FROM public.supplier LIMIT 1")
        return jsonify(status="ok")
    except psycopg.Error:
        return jsonify(status="unavailable"), 503


@app.get("/")
def dashboard():
    with connect() as db:
        counts = {key: db.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(
            sql.Identifier(key))).fetchone()["n"] for key in TABLES}
        low = db.execute("""
            SELECT p.name, p.reorder_level, COALESCE(sum(i.quantity),0) AS stock
            FROM product p LEFT JOIN inventory i USING(product_id)
            GROUP BY p.product_id HAVING COALESCE(sum(i.quantity),0) < p.reorder_level
            ORDER BY stock - p.reorder_level, p.name LIMIT 5
        """).fetchall()
    return render_template("dashboard.html", counts=counts, low=low)


def relation(table):
    if table not in TABLES:
        abort(404)
    return TABLES[table]


def identifiers(fields):
    return sql.SQL(", ").join(map(sql.Identifier, fields))


def key_parts(meta, key):
    pieces = key.split("-")
    if len(pieces) != len(meta.keys) or any(not s.isascii() or not s.isdigit() or
                                           len(s) > 10 or int(s) > 2147483647 for s in pieces):
        abort(404)
    return tuple(map(int, pieces))


def record_key(row, meta):
    return "-".join(str(row[k]) for k in meta.keys)


app.jinja_env.globals["record_key"] = record_key


def by_key(meta):
    return sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in meta.keys)


@app.get("/tables/<table>")
def listing(table):
    meta = relation(table)
    page = max(1, min(request.args.get("page", 1, type=int), 1000000))
    with connect() as db:
        rows = db.execute(sql.SQL("SELECT {} FROM {} ORDER BY {} LIMIT 51 OFFSET %s").format(
            identifiers(meta.columns), sql.Identifier(table), identifiers(meta.keys)),
            ((page - 1) * 50,)).fetchall()
    return render_template("list.html", table=table, meta=meta, rows=rows[:50], page=page, more=len(rows)>50)


def admin_only():
    if g.role != "admin":
        abort(403, "Only an administrator can delete records.")


ERRORS = {"23503": "A related record is missing or another record still refers to this one.",
          "23505": "A record with the same unique value or key already exists.",
          "23514": "Check the quantity, status and date order against the table rules.",
          "23502": "Complete all required fields."}


@app.route("/tables/<table>/new", methods=["GET", "POST"])
@app.route("/tables/<table>/<key>/edit", methods=["GET", "POST"])
def edit(table, key=None):
    meta = relation(table)
    fields = [f for f in meta.fields if key is None or f not in meta.keys]
    args = key_parts(meta, key) if key is not None else ()
    error = None
    with connect() as db:
        row = {}
        parent = None
        if args:
            if table == "order_item" and request.method == "POST":
                parent = lock_order(db, args[0])
            row = db.execute(sql.SQL("SELECT *, xmin::text AS revision FROM {} WHERE {}").format(
                sql.Identifier(table), by_key(meta)) + (sql.SQL(" FOR UPDATE") if request.method == "POST" else sql.SQL("")), args).fetchone()
            if row is None:
                abort(404)
        if request.method == "POST":
            if args and row["revision"] != request.form.get("revision"):
                abort(409, "This record changed. Reopen it before saving.")
            original = dict(row)
            values = [request.form.get(f, "").strip() or None for f in fields]
            row = dict(row, **dict(zip(fields, values)))
            if any(v is None and required(table, f) for f, v in zip(fields, values)):
                error = "Complete all required fields."
            else:
                try:
                    with db.transaction():
                        if table == "order_item" and not args:
                            parent = lock_order(db, row["order_id"])
                        prepare(db, table, original, dict(zip(fields, values)), request.form)
                        if args:
                            assignments = sql.SQL(", ").join(sql.SQL("{}=%s").format(sql.Identifier(f)) for f in fields)
                            result = db.execute(sql.SQL("UPDATE {} SET {} WHERE {}").format(
                                sql.Identifier(table), assignments, by_key(meta)), (*values, *args))
                            if result.rowcount != 1:
                                abort(404)
                        else:
                            db.execute(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                                sql.Identifier(table), identifiers(fields),
                                sql.SQL(", ").join(sql.Placeholder() for _ in fields)), values)
                        if table == "order_item" and parent and parent["status"] == "Confirmed":
                            confirm(db, row["order_id"])
                    flash("Record saved.")
                    return redirect(url_for("listing", table=table))
                except InvalidWorkflow as exc:
                    error = str(exc)
                except (psycopg.IntegrityError, psycopg.DataError) as exc:
                    error = ERRORS.get(exc.sqlstate, "Check the field lengths, numbers and dates.")
        choices = {}
        for f in fields:
            if f in REFERENCES:
                target, label = REFERENCES[f]
                pairs = db.execute(sql.SQL("SELECT {}, {} FROM {} ORDER BY {}").format(
                    sql.Identifier(f), sql.Identifier(label), sql.Identifier(target), sql.Identifier(f))).fetchall()
                choices[f] = [(str(v[f]), f"{v[f]} · {v[label]}") for v in pairs]
            elif (table, f) in OPTIONS:
                choices[f] = [(v, v) for v in OPTIONS[table, f]]
    return render_template("edit.html", table=table, meta=meta, key=key, fields=fields,
                           row=row, choices=choices, error=error), 422 if error else 200


@app.route("/tables/<table>/<key>/delete", methods=["GET", "POST"])
def remove(table, key):
    admin_only()
    meta = relation(table)
    args = key_parts(meta, key)
    with connect() as db:
        if request.method == "POST":
            try:
                if table == "order_item":
                    order = lock_order(db, args[0])
                    if order and order["status"] == "Confirmed":
                        other = db.execute(
                            "SELECT 1 FROM order_item WHERE order_id=%s AND product_id<>%s LIMIT 1", args
                        ).fetchone()
                        if not other:
                            abort(409, "Return the order to Pending before deleting its last item.")
                result = db.execute(sql.SQL("DELETE FROM {} WHERE {} AND xmin::text=%s").format(sql.Identifier(table), by_key(meta)), (*args, request.form.get("revision")))
                if not result.rowcount:
                    abort(409, "This record changed or was deleted. Reopen the table.")
            except psycopg.errors.ForeignKeyViolation:
                db.rollback()
                return render_template("error.html", title="Record is in use",
                                       message=ERRORS["23503"], table=table), 409
            flash("Record deleted.")
            return redirect(url_for("listing", table=table))
        row = db.execute(sql.SQL("SELECT *, xmin::text AS revision FROM {} WHERE {}").format(sql.Identifier(table), by_key(meta)), args).fetchone()
        if row is None:
            abort(404)
    return render_template("delete.html", table=table, meta=meta, row=row, key=key)


@app.errorhandler(psycopg.OperationalError)
def db_error(_exc):
    return render_template("error.html", title="Database unavailable", message="Try again shortly."), 503


@app.errorhandler(HTTPException)
def http_error(exc):
    return render_template("error.html", title=exc.name, message=exc.description), exc.code

