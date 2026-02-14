# Brimley Examples

This directory contains example Brimley functions and configuration to demonstrate the engine's capabilities with Python, SQL, and Template functions.

## 🛠️ Setup

Before running the examples, you must initialize the local SQLite database used by the SQL examples.

```bash
python3 setup_db.py
```

This will create `data.db` and seed it with sample user data.

## 🚀 Running Examples (One-Shot)

You can invoke individual functions using the Brimley CLI from the root of the project.

### 1. SQL Function (`get_users`)

Retrieves users from the database with a limit.

```bash
PYTHONPATH=../src poetry run brimley invoke get_users --root . --input '{limit: 1}'
```

### 2. Python Function (`calculate_tax`)

Calculates tax based on an amount and a rate.

```bash
PYTHONPATH=../src poetry run brimley invoke calculate_tax --root . --input '{amount: 100, rate: 0.2}'
```

### 3. Template Function (`hello`)

Generates a greeting message.

```bash
PYTHONPATH=../src poetry run brimley invoke hello --root . --input '{name: "Developer"}'
```

---

## 🔄 Running via REPL (Interactive)

For a more interactive experience where you can run multiple functions in a single session, use the REPL:

```bash
PYTHONPATH=../src poetry run brimley repl --root .
```

Enable watch mode to auto-reload on file changes:

```bash
PYTHONPATH=../src poetry run brimley repl --root . --watch
```

You can still trigger an on-demand reload with `/reload` in the REPL.

**Inside the REPL:**

```text
brimley > get_users {limit: 1}
# Returns JSON user record

brimley > calculate_tax {amount: 250, rate: 0.15}
# Returns 37.5

brimley > hello {name: "Brimley User"}
# Returns "Hello Brimley User! Welcome to Brimley."

brimley > /quit
```

---

## 🧩 Non-REPL MCP Server

You can run MCP tools without REPL using the first-class CLI command:

```bash
PYTHONPATH=../src poetry run brimley mcp-serve --root .
```

Enable watch mode for automatic tool refresh on file changes:

```bash
PYTHONPATH=../src poetry run brimley mcp-serve --root . --watch
```

Optional host/port overrides:

```bash
PYTHONPATH=../src poetry run brimley mcp-serve --root . --host 127.0.0.1 --port 8000
```

## 📂 File Structure

- `brimley.yaml`: Main configuration (Database definitions, app state).
- `setup_db.py`: Initialization script for the SQLite database.
- `users.sql`: SQL function definition with metadata frontmatter.
- `calc.py`: Python function definition.
- `hello.md`: Template function definition using Jinja2.
