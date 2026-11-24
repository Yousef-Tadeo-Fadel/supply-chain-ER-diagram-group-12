"""Run on a fresh Linux VM as the deployment owner, from the repository root."""
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from credentials import encode


def main():
    private = ROOT / "deploy" / "private"
    if private.exists():
        sys.exit("Private configuration already exists. Preserve it before reconfiguring.")
    ip = str(ipaddress.IPv4Address(input("VM public IPv4 address: ").strip()))
    default_hostname = ip + ".sslip.io"
    hostname = input(f"Public DNS hostname [{default_hostname}]: ").strip().lower() or default_hostname
    if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", hostname):
        sys.exit("Enter a public DNS hostname.")
    accounts = {}
    previous = None
    for username, role in (("admin", "admin"), ("reader", "standard")):
        password = getpass.getpass(f"New private password for {username} (at least 16 characters): ")
        if (len(password) < 16 or password == previous or
                password in ("Classroom-Admin-12", "Classroom-Reader-12")):
            sys.exit("Use a different private password of at least 16 characters for each account.")
        if password != getpass.getpass("Repeat password: "):
            sys.exit("Passwords did not match.")
        accounts[username] = {"role": role, "hash": encode(password)}
        previous = password
    os.umask(0o077)
    private.mkdir(mode=0o700)
    accounts_file = private / "accounts.json"
    accounts_file.write_text(json.dumps(accounts), encoding="utf-8")
    # The private parent restricts host access; the container's non-root user needs to read the bind mount.
    accounts_file.chmod(0o444)
    values = {"POSTGRES_PASSWORD": secrets.token_hex(32), "WEB_DB_PASSWORD": secrets.token_hex(32),
              "SESSION_SECRET": secrets.token_hex(48), "PUBLIC_IP": ip, "SITE_NAME": hostname}
    (private / "production.env").write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    print("Private configuration created.")


if __name__ == "__main__":
    main()

