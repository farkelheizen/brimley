# Brimley Oracle Example

This is an optional Brimley example workspace for Oracle-backed SQL tools.

The layout is intentionally split:

- `oracle_examples/` holds Docker and local environment assets.
- `oracle_examples/app/` holds only Brimley-scannable application files.

That keeps `docker-compose` files, `.env` files, and other support assets out of the Brimley scanner path.

## What This Example Shows

- Oracle connectivity through SQLAlchemy and the optional `oracledb` driver.
- A Brimley `@on_startup` hook that creates and seeds demo tables.
- SQL tools that query and mutate Oracle data through a pooled `default` engine.

## Prerequisites

From the repository root, install the optional Oracle driver:

```bash
poetry install -E oracle
```

You also need Docker and an Oracle Container Registry login.

Oracle publishes the safest default image for this example at:

```text
container-registry.oracle.com/database/free:latest
```

If `docker compose pull` or `docker compose up` fails with an authorization error, sign in to Oracle Container Registry and accept the Oracle Database Free repository terms first.

## Start Oracle Free

Change into the example workspace:

```bash
cd oracle_examples
```

Create a local `.env` file from `.env.example`, then export it into your current shell before running Brimley:

```bash
set -a
source .env
set +a
```

Start the container:

```bash
docker compose up -d
```

Watch startup logs until Oracle prints:

```text
DATABASE IS READY TO USE!
```

Example:

```bash
docker compose logs -f oracle-free
```

## Initialize the Brimley App

The example schema is created by a Brimley startup hook in `app/bootstrap.py`.

Because Brimley startup hooks run in `repl` and `mcp-serve` modes, but not `invoke`, initialize the schema once with REPL mode:

```bash
PYTHONPATH=../src poetry run brimley repl --root ./app --no-watch --no-mcp
```

After startup completes, the hook will create:

- `brimley_demo_customers`
- `brimley_demo_startup_events`

and seed a few demo customer rows if the customer table is empty.

You can then exit the REPL.

## Invoke the SQL Tools

List customers:

```bash
PYTHONPATH=../src poetry run brimley invoke list_customers --root ./app --input '{}'
```

Look up a single customer by email:

```bash
PYTHONPATH=../src poetry run brimley invoke get_customer_by_email --root ./app --input '{email: "ada@example.com"}'
```

Insert a new customer:

```bash
PYTHONPATH=../src poetry run brimley invoke add_customer --root ./app --input '{email: "new@example.com", full_name: "New Person", status: "active"}'
```

Inspect startup events written by the startup hook:

```bash
PYTHONPATH=../src poetry run brimley invoke list_startup_events --root ./app --input '{}'
```

## Connection Notes

This example uses the Oracle Free defaults documented by Oracle Database containers:

- SID: `FREE`
- PDB / service name: `FREEPDB1`
- schema user for this example: `pdbadmin`

The Brimley app reads these values from shell environment variables referenced in `app/brimley.yaml`.

## Cleanup

Stop the local Oracle container:

```bash
docker compose down
```

Remove the persisted Oracle volume too:

```bash
docker compose down -v
```