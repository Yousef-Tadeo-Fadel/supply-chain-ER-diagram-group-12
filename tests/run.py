"""Start a uniquely named, unpublished Docker project and run the HTTP tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
project = "cmpe341test" + uuid4().hex
env = {k: v for k, v in os.environ.items() if not k.upper().startswith("COMPOSE_")}
env.update(DB_CONTAINER_NAME=project + "-db", WEB_CONTAINER_NAME=project + "-app",
           POSTGRES_PASSWORD=uuid4().hex, WEB_DB_PASSWORD=uuid4().hex)
cmd = ["docker", "compose", "--env-file", str(root / "tests" / "empty.env"), "-p", project,
       "-f", "compose.yaml", "-f", "tests/compose.yaml"]


def run(*args, check=True):
    return subprocess.run(cmd + list(args), env=env, cwd=root, check=check)


def verify_isolation(config):
    def require(ok, message):
        if not ok:
            raise ValueError("Unsafe test configuration: " + message)

    require(config["name"] == project, "unexpected Compose project")
    services = config["services"]
    require(set(services) == {"db", "app", "provision"}, "unexpected services")
    require(set(config["networks"]) == {"default"} and
            config["networks"]["default"]["name"] == project + "_default" and
            not config["networks"]["default"].get("external"), "shared network")
    for name, service in services.items():
        require(not service.get("ports") and not service.get("network_mode"), "published or shared networking")
        require(set(service["networks"]) == {"default"}, "unexpected network")
        expected = None if name == "provision" else project + "-" + name
        require(service.get("container_name") == expected, "shared container name")
        mounts = {m["target"]: m for m in service.get("volumes", [])}
        expected_targets = {"db": {"/var/lib/postgresql/data", "/docker-entrypoint-initdb.d"},
                            "app": {"/checks"}, "provision": set()}
        require(set(mounts) == expected_targets[name], "unexpected filesystem mount")
        for target, mount in mounts.items():
            if target == "/var/lib/postgresql/data":
                require(mount["type"] == "tmpfs" and not mount.get("source"), "persistent database storage")
            else:
                folder = "sql" if name == "db" else "tests"
                require(mount["type"] == "bind" and mount.get("read_only") and
                        Path(mount["source"]).resolve() == (root / folder).resolve(), "unexpected bind mount")
        settings = service["environment"]
        key = "POSTGRES_DB" if name == "db" else "DB_NAME"
        require(settings[key] == "cmpe341_http_test", "unexpected database")
        if name != "db":
            require(settings["DB_HOST"] == "db", "external database host")


if __name__ == "__main__":
    config = json.loads(subprocess.check_output(cmd + ["config", "--format", "json"], env=env, cwd=root))
    verify_isolation(config)
    if sys.argv[1:] == ["--check-only"]:
        print("PASS: isolated project, RAM-only database, read-only source mounts and no host ports.")
        sys.exit(0)
    if sys.argv[1:]:
        sys.exit("Usage: python tests/run.py [--check-only]")
    engine = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if engine.returncode:
        sys.exit("Docker Engine is unavailable to this terminal. No test containers were started.")
    label = "label=com.docker.compose.project=" + project
    for resource in ("container", "network", "volume"):
        args = ["docker", resource, "ls", "-q", "--filter", label]
        if resource == "container":
            args.append("--all")
        if subprocess.check_output(args, env=env).strip():
            sys.exit("Generated test project already exists. No changes made.")
    try:
        run("up", "--build", "--wait", "--wait-timeout", "180")
        run("exec", "-T", "app", "python", "/checks/http_checks.py")
        run("restart", "app")
        run("up", "--wait", "--wait-timeout", "180")
        run("exec", "-T", "app", "python", "/checks/http_checks.py", "--verify-seed")
    except subprocess.CalledProcessError:
        run("ps", "-a", check=False)
        run("logs", "--tail", "60", "db", "provision", "app", check=False)
        sys.exit(1)
    finally:
        # PostgreSQL lives in the test container's tmpfs. Never request volume deletion.
        run("down", check=True)

