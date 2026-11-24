"""Checks that can run without Docker Engine, PostgreSQL or third-party Python packages."""
import ast
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import run as runner

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "app"), str(ROOT / "deploy")]
import configure
import start
from catalog import TABLES
from credentials import matches
from workflows import InvalidWorkflow, confirm, receive, validate_price


class ProjectChecks(unittest.TestCase):
    def test_vm_launcher(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(configure, "ROOT", Path(temp)), \
                patch.object(configure, "main") as setup, patch("subprocess.run") as launch:
            start.main()
            setup.assert_called_once()
            args = [call.args[0] for call in launch.call_args_list]
            self.assertEqual(args[1][-2:], ["config", "--quiet"])
            self.assertIn("compose.production.yaml", args[2])
            self.assertIn("--wait", args[2])
            self.assertTrue(all(call.kwargs["check"] for call in launch.call_args_list))
            private = Path(temp) / "deploy/private"
            private.mkdir(parents=True)
            (private / "production.env").touch()
            setup.reset_mock()
            start.main()
            setup.assert_not_called()

    def test_schema_and_seed(self):
        # SQLite is used only to independently check fixture content and key mappings.
        with sqlite3.connect(":memory:") as db:
            db.execute("PRAGMA foreign_keys=ON")
            schema = (ROOT / "sql/01_schema.sql").read_text(encoding="utf-8")
            db.executescript(schema.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT"))
            db.executescript((ROOT / "sql/02_data.sql").read_text(encoding="utf-8"))
            counts = {}
            for name, table in TABLES.items():
                info = db.execute(f"PRAGMA table_info({name})").fetchall()
                self.assertEqual(set(table.columns), {c[1] for c in info})
                self.assertEqual(table.keys, tuple(c[1] for c in sorted(info, key=lambda c: c[5]) if c[5]))
                counts[name] = db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            tree = ast.parse((ROOT / "tests/http_checks.py").read_bytes())
            expected = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                            and getattr(n.targets[0], "id", "") == "SEED_COUNTS")
            self.assertEqual(counts, expected)
            self.assertEqual(sum(counts.values()), 56)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            queries = (ROOT / "queries/03_queries.sql").read_text(encoding="utf-8").split(";")
            detail, totals, low = [db.execute(q).fetchall() for q in queries if q.strip()]
            self.assertEqual((len(detail), len(totals)), (10, 4))
            self.assertEqual({row[1] for row in low}, {"Stretch Wrap Rolls", "Packing Tape Rolls"})

    def test_prices(self):
        for price in ("12.50", "0.01"):
            validate_price({"unit_price": price})
        for price in ("0", "-1", "0.001", "NaN", "Infinity", "boxes"):
            with self.subTest(price=price), self.assertRaises(InvalidWorkflow):
                validate_price({"unit_price": price})

    def test_demo_accounts(self):
        accounts = json.loads((ROOT / "app/demo-accounts.json").read_text())
        for user, role, password in (("admin", "admin", "Classroom-Admin-12"),
                                     ("reader", "standard", "Classroom-Reader-12")):
            self.assertEqual(accounts[user]["role"], role)
            self.assertTrue(matches(password, accounts[user]["hash"]))
            self.assertFalse(matches("wrong", accounts[user]["hash"]))

    def test_partial_receipt_and_remaining_quantity(self):
        db = Mock()
        values = {"product_id": "1", "warehouse_id": "2", "quantity": "5", "status": "Partially Received"}
        receive(db, {}, values, {"delivery_units": "2"})
        self.assertEqual(db.execute.call_args.args[1], ("2", "1", 2))
        db.reset_mock()
        with self.assertRaises(InvalidWorkflow):
            receive(db, values, dict(values, status="Received"), {"earlier_units": "9"})
        db.execute.assert_not_called()
        received = dict(values, status="Received")
        receive(db, values, received, {"earlier_units": "2"})
        self.assertEqual(db.execute.call_args.args[1], ("2", "1", 3))
        db.reset_mock()
        receive(db, received, received, {})
        db.execute.assert_not_called()

    def test_confirmation_checks_available_stock(self):
        for needed, available, valid in [(3, [1, 2], True), (4, [1, 2], False), (1, [], False)]:
            db = Mock()
            db.execute.return_value.fetchall.side_effect = [
                [{"product_id": 1, "quantity": needed}], [{"quantity": n} for n in available]]
            if valid:
                confirm(db, 22)
            else:
                with self.assertRaises(InvalidWorkflow):
                    confirm(db, 22)
        db = Mock()
        db.execute.return_value.fetchall.return_value = []
        with self.assertRaises(InvalidWorkflow):
            confirm(db, 22)

    def test_vm_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "deploy").mkdir()
            passwords = ["TestOnly-One-Long-Password", "TestOnly-Two-Long-Password"]
            with patch.object(configure, "ROOT", root), patch("builtins.input", side_effect=["192.0.2.1", ""]), \
                    patch("getpass.getpass", side_effect=[p for p in passwords for _ in range(2)]):
                previous_mask = os.umask(0o077)
                try:
                    configure.main()
                    with self.assertRaises(SystemExit):
                        configure.main()
                finally:
                    os.umask(previous_mask)
            private = root / "deploy/private"
            accounts_file = private / "accounts.json"
            try:
                accounts = json.loads(accounts_file.read_text())
                env_file = (private / "production.env").read_text()
                self.assertIn("SITE_NAME=192.0.2.1.sslip.io", env_file)
                for user, pwd in zip(("admin", "reader"), passwords):
                    self.assertTrue(matches(pwd, accounts[user]["hash"]))
                    self.assertNotIn(pwd, env_file + accounts_file.read_text())
            finally:
                accounts_file.chmod(0o600)


class IsolationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 'compose config' is an offline parser. It makes no Engine requests.
        cls.config = json.loads(subprocess.check_output(
            runner.cmd + ["config", "--format", "json"], cwd=ROOT, env=runner.env))

    def test_intended_project(self):
        runner.verify_isolation(self.config)

    def test_rejects_persistent_data_and_shared_resources(self):
        for scenario in ("live-volume", "external-db", "fixed-name", "writable-sql", "published-port",
                         "shared-network", "wrong-project", "live-db-name"):
            with self.subTest(scenario=scenario):
                config = copy.deepcopy(self.config)
                db = config["services"]["db"]
                app = config["services"]["app"]
                if scenario == "live-volume":
                    mount = next(m for m in db["volumes"] if m["target"] == "/var/lib/postgresql/data")
                    mount.update(type="volume", source="postgres_fixed_data")
                elif scenario == "external-db":
                    app["environment"]["DB_HOST"] = "host.docker.internal"
                elif scenario == "fixed-name":
                    db["container_name"] = "supply_chain_postgres"
                elif scenario == "writable-sql":
                    next(m for m in db["volumes"] if m["type"] == "bind")["read_only"] = False
                elif scenario == "published-port":
                    db["ports"] = [{"published": "5432"}]
                elif scenario == "shared-network":
                    config["networks"]["default"]["external"] = True
                elif scenario == "wrong-project":
                    config["name"] = "supplychaindb"
                else:
                    db["environment"]["POSTGRES_DB"] = "supply_chain_db"
                with self.assertRaises(ValueError):
                    runner.verify_isolation(config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
