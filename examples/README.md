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

## 🧩 External MCP Embedding Example

Brimley MCP tools can be registered in a standalone or pre-existing FastMCP server without running the Brimley REPL.

Example script:

```bash
PYTHONPATH=../src python3 mcp_external_embedding.py
```

The script demonstrates:

- `build_mcp_server(root_dir)`: create a new FastMCP server and register Brimley tools.
- `register_on_existing_server(root_dir, server)`: attach Brimley tools to an existing FastMCP server.
- `run_host_auto_reload_demo(root_dir)`: host-managed auto-reload with `BrimleyRuntimeController` + external MCP refresh callback.

If FastMCP is not installed, the script prints a friendly message and exits.

## 📂 File Structure

- `brimley.yaml`: Main configuration (Database definitions, app state).
- `setup_db.py`: Initialization script for the SQLite database.
- `users.sql`: SQL function definition with metadata frontmatter.
- `calc.py`: Python function definition.
- `hello.md`: Template function definition using Jinja2.
- `mcp_external_embedding.py`: Programmatic MCP embedding example with `BrimleyMCPAdapter`.
