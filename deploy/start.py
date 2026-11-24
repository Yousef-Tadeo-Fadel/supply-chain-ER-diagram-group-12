"""Start the Group 12 production stack on its Linux VM."""
import subprocess

import configure


def main():
    root = configure.ROOT
    compose = ["sudo", "docker", "compose"]
    subprocess.run(compose + ["version"], cwd=root, check=True)
    private_env = root / "deploy" / "private" / "production.env"
    if not private_env.is_file():
        configure.main()
    compose += ["--env-file", str(private_env), "-f", "compose.yaml", "-f", "compose.production.yaml"]
    for args in (["config", "--quiet"], ["up", "--build", "-d", "--wait", "--wait-timeout", "240"],
                 ["ps", "-a"]):
        subprocess.run(compose + args, cwd=root, check=True)
    subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, check=True)


if __name__ == "__main__":
    main()
