# Brimley Examples

> Version 0.5

This directory contains example Brimley functions and configuration to demonstrate the engine's capabilities with Python, SQL, and Template functions.

## 🛠️ Setup

Before running the examples, you must initialize the local SQLite database used by the SQL examples.

```bash
poetry run python setup_db.py
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

Calculates tax based on an amount and a rate (decorator-based Python function).

```bash
PYTHONPATH=../src poetry run brimley invoke calculate_tax --root . --input '{amount: 100, rate: 0.2}'
```

### 3. Template Function (`hello`)

Generates a greeting message.

```bash
PYTHONPATH=../src poetry run brimley invoke hello --root . --input '{name: "Developer"}'
```

### 4. Python Agent Function (`agent_sample`)

Demonstrates decorator-based MCP tool behavior and context injection in a Python function (`mcp_ctx: Context`) with `session.sample(...)`.

Run this in REPL to use the local mock MCP context:

```bash
PYTHONPATH=../src poetry run brimley repl --root .
```

Then execute:

```text
brimley > agent_sample {prompt: "Summarize the Brimley project in one line."}
# Prints [Mock Sampling] in the terminal and returns a mock sample payload
```

### 5. Python Nested Function Composition (`nested_greeting`)

Demonstrates a decorator-based Python function receiving `BrimleyContext` and executing another Brimley function by name.

```bash
PYTHONPATH=../src poetry run brimley invoke nested_greeting --root . --input '{name: "Composer"}'
```

This calls `hello` internally via `ctx.execute_function_by_name(...)`.

### 6. Python File Hash Function (`sha256_file`)

Calculates a SHA256 digest for a file path.

```bash
PYTHONPATH=../src poetry run brimley invoke sha256_file --root . --input '{filepath: "../README.md"}'
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

brimley > agent_sample {prompt: "Summarize Brimley in one line."}
# Prints [Mock Sampling] and returns a dict with sample_text/model metadata

brimley > sha256_file {filepath: "../README.md"}
# Returns SHA256 digest string

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
- `calc.py`: Decorator-based Python function definition.
- `agent_sample.py`: Decorator-based Python function using MCP context injection and `session.sample(...)`.
- `nested_greeting.py`: Decorator-based Python function that composes another Brimley function by name via `BrimleyContext`.
- `sha256_file.py`: Decorator-based Python function that computes SHA256 digest for a file path.
- `hello.md`: Template function definition using Jinja2.
