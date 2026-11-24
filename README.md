# CMPE341 Supply Chain Management · Group 12

## Local classroom demo

With Docker Desktop or Docker Engine and Compose 2.24.4+ installed, run the following from a checkout containing the application. The default configuration uses loopback ports 8000 and 5432. If your original Desktop project is already running, use the classroom instructions below to open Section 6 alongside it.

```sh
docker compose up
```

Open [the dashboard](http://127.0.0.1:8000). These public accounts are for the local classroom demo.

| Username | Password | Access |
| --- | --- | --- |
| admin | Classroom-Admin-12 | Read, create, edit and delete |
| reader | Classroom-Reader-12 | Read, create and edit |

Choose a table on the dashboard to manage records. Inventory and Order Item use both key columns. Admin deletion requires a confirmation form and PostgreSQL rejects deleting a referenced parent. Password verifiers use salted scrypt. Signed session cookies, server-side session expiry, CSRF tokens and server-side role checks protect the forms. The app connects through a dedicated database login with table and sequence privileges. Employee job titles are separate from login roles.

Receiving a purchase posts stock and changes the order in one transaction. For an existing partial order, the operator supplies the cumulative earlier quantity from receiving documents. The business schema has no receipt ledger. Confirming a sales order checks availability across warehouses without reserving stock.

### Open Section 6 alongside the original Desktop project

From this checkout, run the following in the VS Code terminal. The classroom project gets its own containers and PostgreSQL volume. It publishes only the web app on port 8001.

```powershell
docker compose -p cmpe341-group12-classroom -f compose.yaml -f compose.classroom.yaml up --build -d --wait
```

Open [the Section 6 sign-in page](http://127.0.0.1:8001/login). Sign in as `reader` to see the dashboard and edit records. Sign out and sign in as `admin` to see the delete action. To stop the classroom copy while keeping its records, run `docker compose -p cmpe341-group12-classroom -f compose.yaml -f compose.classroom.yaml stop`.

## Verification and original data

From a Windows terminal with Docker access, run:

```powershell
python tests/run.py
```

The runner checks the rendered Compose configuration before starting anything. The test uses a randomly named project and a RAM-backed PostgreSQL database named `cmpe341_http_test`. It publishes no ports, mounts the SQL and test directories read-only, and refuses existing resources carrying the generated project label. Cleanup stops and removes that test project without requesting volume deletion. Run `python tests/run.py --check-only` to verify isolation without connecting to Docker Engine.

The suite submits HTTP forms for both roles and all ten tables, checks PostgreSQL constraints and stock workflows, and compares every seed row after deleting its own fixtures. GitHub Actions runs the same suite on push. A successful **Docker integration** run for the submitted commit provides runtime evidence without a second run on a personal laptop.

The original SQL lives in sql/ and queries/. The initialization scripts run on a fresh volume. To adopt changes in an existing installation, retain the original project directory, Compose project name, private .env and postgres_fixed_data volume. Back up the live database first. Never use volume removal on the original project.

## Submission

[Group 12 repository](https://github.com/Yousef-Tadeo-Fadel/supply-chain-ER-diagram-group-12). Publish only the reviewed source and classroom fixtures. Keep .env files, deploy/private/, private keys and backups outside Git. The repository owner verifies public visibility and invites the group members in Settings → Collaborators. Record the URL in the instructor's shared spreadsheet. See [Linux deployment](docs/Linux-deployment.md) for Chapter 7.
