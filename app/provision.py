"""Install only the web login and its DML grants. Business DDL lives in sql/."""
import os

from psycopg import sql
from catalog import TABLES
from db import connect


def provision():
    role = "cmpe341_web"
    with connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(34112)")
        found = db.execute(
            "SELECT rolcomment.description FROM pg_roles r LEFT JOIN pg_shdescription rolcomment "
            "ON rolcomment.objoid = r.oid AND rolcomment.classoid = 'pg_authid'::regclass "
            "WHERE r.rolname = %s", (role,)
        ).fetchone()
        if found and found["description"] != "CMPE341 application login":
            raise RuntimeError("The requested database role already exists and is unmanaged.")
        if not found:
            db.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
            db.execute(sql.SQL("COMMENT ON ROLE {} IS 'CMPE341 application login'").format(sql.Identifier(role)))
        db.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
            sql.Identifier(role), sql.Literal(os.environ["WEB_DB_PASSWORD"])))
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        for name, table in TABLES.items():
            db.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON public.{} TO {}").format(
                sql.Identifier(name), sql.Identifier(role)))
            if len(table.keys) == 1:
                seq = db.execute("SELECT pg_get_serial_sequence(%s, %s) AS seq",
                                 ("public." + name, table.keys[0])).fetchone()["seq"]
                schema, sequence = seq.split(".")
                db.execute(sql.SQL("GRANT USAGE ON SEQUENCE {}.{} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(sequence), sql.Identifier(role)))


if __name__ == "__main__":
    provision()

