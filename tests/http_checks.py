"""Exercise real Gunicorn HTTP routes and inspect committed rows via the web DB role."""
from http.cookiejar import CookieJar
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request

sys.path.insert(0, "/app")
from psycopg import sql
from catalog import TABLES
from db import connect

# Counts in the group's checked-in sql/02_data.sql, including both junction tables.
SEED_COUNTS = {
    "supplier": 3, "warehouse": 3, "customer": 4, "product": 6, "employee": 5,
    "inventory": 13, "purchase_order": 4, "sales_order": 5, "order_item": 10, "shipment": 3,
}


class Form(HTMLParser):
    csrf = None
    revision = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "csrf":
            self.csrf = attrs["value"]
        if tag == "input" and attrs.get("name") == "revision":
            self.revision = attrs["value"]


class Browser:
    def __init__(self):
        self.http = build_opener(HTTPCookieProcessor(CookieJar()))
        self.token = ""
        self.revision = ""

    def visit(self, path, data=None, status=200, final=None):
        body = None if data is None else urlencode({"csrf": self.token, "revision": self.revision, **data}).encode()
        try:
            reply = self.http.open(Request("http://127.0.0.1:8000" + path, data=body), timeout=15)
        except HTTPError as exc:
            reply = exc
        with reply:
            content = reply.read().decode()
            assert reply.status == status, (path, reply.status, status, content[-700:])
            if final:
                assert reply.geturl().endswith(final), (path, reply.geturl())
        form = Form()
        form.feed(content)
        if form.csrf:
            self.token = form.csrf
        self.revision = form.revision or ""
        return content

    def login(self, username, password):
        self.visit("/login")
        self.visit("/login", {"username": username, "password": password}, final="/")


def snapshot(db):
    return {t: db.execute(sql.SQL("SELECT * FROM {} ORDER BY {}").format(
        sql.Identifier(t), sql.SQL(", ").join(map(sql.Identifier, meta.keys)))).fetchall()
            for t, meta in TABLES.items()}


def main():
    # This file is mounted only by tests/compose.yaml. Require proof of test context.
    import os
    if os.environ.get("ISOLATED_HTTP_TEST") != "1":
        raise RuntimeError("Use the isolated Docker test runner.")
    with connect() as db:
        db.autocommit = True
        if db.execute("SELECT current_database() AS name").fetchone()["name"] != "cmpe341_http_test":
            raise RuntimeError("Refusing to run HTTP checks against this database.")
        before = snapshot(db)
        counts = {table: len(rows) for table, rows in before.items()}
        assert counts == SEED_COUNTS, (counts, SEED_COUNTS)
        if "--verify-seed" in sys.argv:
            browser = Browser()
            browser.login("reader", "Classroom-Reader-12")
            dashboard = browser.visit("/")
            assert all(meta.title in dashboard for meta in TABLES.values())
            print("PASS: fresh sign-in and ten-table dashboard after restart; 56 seed rows present.")
            return
        check_routes(db, before)


def check_routes(db, before):
    admin = Browser()
    reader = Browser()
    admin.visit("/", final="/login")
    admin.visit("/health")
    reader.visit("/login")
    reader.visit("/login", {"username": "reader", "password": "incorrect"}, status=401)
    reader.login("reader", "Classroom-Reader-12")
    admin.login("admin", "Classroom-Admin-12")
    for table, meta in TABLES.items():
        path = "/tables/" + table
        key = "-".join(str(before[table][0][c]) for c in meta.keys)
        assert "Add record" in reader.visit(path)
        reader.visit(path + "/new")
        reader.visit(f"{path}/{key}/edit")
        for url in (f"{path}/{key}/delete",):
            reader.visit(url, status=403)
            reader.visit(url, {}, status=403)

    admin.visit("/tables/supplier/new", {"csrf": ""}, status=400)
    admin.visit("/tables/unknown", status=404)
    admin.visit("/tables/inventory/1/edit", status=404)
    print("PASS: login, logout, CSRF, unknown tables, composite key validation and standard-role deletion restrictions.")
    created = {}
    for table, values, change in fixtures(created):
        path = "/tables/" + table
        reader.visit(path + "/new")
        old = snapshot(db)[table]
        reader.visit(path + "/new", values, final=path)
        new = [r for r in snapshot(db)[table] if r not in old]
        assert len(new) == 1, (table, new)
        keys = TABLES[table].keys
        key = "-".join(str(new[0][c]) for c in keys)
        created[table] = key
        edit = f"{path}/{key}/edit"
        reader.visit(edit)
        payload = {k: v for k, v in values.items() if k not in keys}
        reader.visit(edit, {**payload, **change}, final=path)
        row = next(r for r in snapshot(db)[table] if all(r[c] == new[0][c] for c in keys))
        assert all(str(row[c]) == str(v) for c, v in change.items())
        if table == "inventory":
            admin.visit(edit)
            admin.visit(edit, {"quantity": -1}, status=422)
            admin.visit(path + "/new", values, status=422)
        print(f"PASS: {table} insert, list and update.")
    reader.visit("/logout", {}, final="/login")
    reader.visit("/tables/supplier", final="/login")
    workflows(admin, db, created)
    admin.visit(f"/tables/supplier/{created['supplier']}/delete")
    assert "Record is in use" in admin.visit(f"/tables/supplier/{created['supplier']}/delete", {}, status=409)
    for table, key in reversed(list(created.items())):
        path = "/tables/" + table
        admin.visit(f"{path}/{key}/delete")
        admin.visit(f"{path}/{key}/delete", {}, final=path)
        admin.visit(f"{path}/{key}/edit", status=404)
    assert snapshot(db) == before
    print("PASS: protected parent deletion, all ten deletes and complete seed row equality.")


def workflows(admin, db, ids):
    po = f"/tables/purchase_order/{ids['purchase_order']}/edit"
    base = dict(product_id=ids["product"], warehouse_id=ids["warehouse"], employee_id=ids["employee"],
                quantity=4, order_date="2026-11-20")
    def units():
        return db.execute("SELECT quantity FROM inventory WHERE warehouse_id=%s AND product_id=%s",
                          (ids["warehouse"], ids["product"])).fetchone()["quantity"]
    start = units()
    admin.visit(po)
    stale = admin.revision
    admin.visit(po, dict(base, status="Partially Received", delivery_units=1), final="/tables/purchase_order")
    assert units() == start + 1
    admin.visit(po, dict(base, status="Partially Received", delivery_units=1, revision=stale), status=409)
    assert units() == start + 1
    admin.visit(po)
    admin.visit(po, dict(base, status="Received", earlier_units=1), final="/tables/purchase_order")
    assert units() == start + 4
    order = f"/tables/sales_order/{ids['sales_order']}/edit"
    line = f"/tables/order_item/{ids['order_item']}/edit"
    payload = dict(customer_id=ids["customer"], order_date="2026-11-21", status="Confirmed")
    admin.visit(line)
    admin.visit(line, {"quantity": 10000}, final="/tables/order_item")
    admin.visit(order)
    admin.visit(order, payload, status=422)
    admin.visit(line)
    admin.visit(line, {"quantity": 2}, final="/tables/order_item")
    admin.visit(order)
    admin.visit(order, payload, final="/tables/sales_order")
    delete_line = f"/tables/order_item/{ids['order_item']}/delete"
    admin.visit(delete_line)
    assert "last item" in admin.visit(delete_line, {}, status=409)
    admin.visit(order)
    admin.visit(order, dict(payload, status="Pending"), final="/tables/sales_order")
    print("PASS: partial and final receipts, stale replay, stock checks and last confirmed item protection.")


def fixtures(ids):
    yield "supplier", dict(name="Test Supply", country="Türkiye", email="test@example.test",
                           lead_time_days=2), {"lead_time_days": 3}
    yield "warehouse", dict(name="Test warehouse", city="Ankara", capacity=400), {"capacity": 450}
    yield "customer", dict(name="Test customer"), {"name": "Revised customer"}
    yield "product", dict(name="Test product", category="Boxes", unit_price="2.40", reorder_level=2,
                          supplier_id=ids["supplier"]), {"unit_price": "3.50"}
    yield "employee", dict(name="Test staff", role="Purchasing Officer", warehouse_id=ids["warehouse"]), {"name": "Revised staff"}
    yield "inventory", dict(warehouse_id=ids["warehouse"], product_id=ids["product"], quantity=0), {"quantity": 8}
    yield "purchase_order", dict(product_id=ids["product"], warehouse_id=ids["warehouse"],
                                 employee_id=ids["employee"], quantity=4, order_date="2026-11-20",
                                 status="Ordered"), {"status": "In Transit"}
    yield "sales_order", dict(customer_id=ids["customer"], order_date="2026-11-20", status="Pending"), {"order_date": "2026-11-21"}
    yield "order_item", dict(order_id=ids["sales_order"], product_id=ids["product"], quantity=1), {"quantity": 2}
    yield "shipment", dict(order_id=ids["sales_order"], warehouse_id=ids["warehouse"],
                           employee_id=ids["employee"], carrier_name="Test carrier", status="Preparing"), {"status": "Shipped"}


if __name__ == "__main__":
    main()

