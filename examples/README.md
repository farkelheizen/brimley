# Brimley Examples

> **Note:** The version header is kept at `0.6.x` for the pre-existing examples. New 0.7 additions are described in the **What's New in 0.7** section above.

> Examples baseline: 0.9.1

This directory contains exploratory Brimley examples and configuration for Python, SQL, and Template functions.

These examples are for development iteration and behavior validation. They are not production deployment guidance.

This directory remains the SQLite-first baseline example set.

If you want the optional Oracle walkthrough, use `oracle_examples/README.md`. That example keeps Docker and shell environment files outside the Brimley scan root and uses `oracle_examples/app/` as the application subtree.

## What's New in 0.9

Brimley 0.9 establishes the application server boundary and introduces Managed Tasks:

- **`@function(task={...})`** (`task_reconciler.py`): marks an async function as a periodic managed task; scheduling is described inline via `interval`, `immediate`, `retries`, and `retry_interval` parameters.
- **`TaskScheduler`**: discovered task functions are registered with the scheduler automatically. The scheduler runs on a dedicated daemon thread with its own event loop. It starts in `repl` and `mcp-serve` modes; skipped in `invoke` mode.
- **`/tasks` REPL command**: lists all task functions, their scheduling configuration, current state, failure count, last run time, and next scheduled run.
- **`mcp-serve --transport stdio`**: the `mcp-serve` command now accepts a `--transport` flag (`sse` or `stdio`) to select the MCP transport protocol. Useful for local MCP client connections (Claude Desktop, VS Code).
- **Embedding removed**: `BrimleyRuntimeController` is no longer part of the public API. The three supported runtime modes are `repl`, `mcp-serve`, and `invoke`.

## What's New in 0.8

Brimley 0.8 introduces a managed dependency injection (DI) system:

- **`@provider`** (`di_provider.py`): marks a function (or generator) as a DI-managed singleton or request-scoped dependency; supports yield-based setup/teardown.
- **`@on_startup`** (`di_provider.py`): lifecycle hook called after all eager singletons are initialized; receives `BrimleyContext`.
- **`@on_shutdown`**: lifecycle hook called on graceful shutdown; executes in reverse declaration order.
- **`Depends(name)`** (`di_provider.py`): default value marker used in `@function` signatures to inject a named provider; resolved by the container at call time.
- **`BrimleyContext`** is now importable directly from `brimley` (`from brimley import BrimleyContext`).

## What's New in 0.7

Brimley 0.7 introduces two new function types:

- **`api_function`** (`github_profile.yaml`): HTTP API calls via `httpx` with Jinja2 templating, `secrets:` block, and per-status-code `results:` handling.
- **`cli_function`** (`system_metrics.yaml`): subprocess execution via `asyncio.create_subprocess_exec` with `command_arguments:`, timeout enforcement, and per-exit-code `results:` parsing.

Both function types are MCP-exposed as tools and support the same `secrets:`, `arguments:`, and `results:` schema.

## What's New in 0.6

Brimley 0.6 introduces structured logging. The `brimley.yaml` now includes a top-level `logging:` block that configures:

- A stderr sink (always active, required for MCP transport).
- An optional file sink at `./logs/brimley.log` with rotation and retention.
- Per-module level overrides (`fastmcp`, `sqlalchemy`, etc.).
- JSONL format support for structured log analysis.

After running any invoke command you should now see a `logs/brimley.log` file created in this directory. The `logs/` directory is excluded from version control via `.gitignore`.

## � Keeping Examples Current

Examples must be updated whenever a new Brimley version introduces a user-visible feature or API change that affects them. When adding or merging a plan:

- Update the version header above to match the release.
- Add, update, or remove example files and CLI invocations to reflect the new behavior.
- If the `brimley.yaml` config schema changes, update `examples/brimley.yaml` accordingly.

---

## �🛠️ Setup

### Optional: Install fastmcp

The MCP-related examples (`agent_sample`, `mcp-serve`) require `fastmcp`, which is an optional dependency. Install it with:

```bash
poetry add fastmcp
```

### Database

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

### 7. API Function (`get_github_profile`)

Fetches a public GitHub user profile using the GitHub REST API. Requires a valid `GITHUB_TOKEN` environment variable.

```bash
GITHUB_TOKEN=your_token PYTHONPATH=../src poetry run brimley invoke get_github_profile --root . --input '{"username": "octocat"}'
```

### 8. CLI Function (`get_system_load`)

Returns the current system load average using the `uptime` command. Demonstrates per-exit-code `results:` parsing with a regex capture group.

```bash
PYTHONPATH=../src poetry run brimley invoke get_system_load --root . --input '{}'
```

### 9. DI Provider Function (`greet_with_counter`)

Demonstrates dependency injection: the `RequestCounter` singleton is initialized by `@provider`, and `Depends("request_counter")` injects it into the function automatically.

```bash
PYTHONPATH=../src poetry run brimley invoke greet_with_counter --root . --input '{"name": "Alice"}'
```

### 10. Task Function (`reconciler`)

Demonstrates a managed task function declared with `@function(task={...})`. The `reconciler` task runs every 30 seconds with `immediate=True` (runs once at startup), retries up to 3 times on failure, and uses exponential backoff between retries.

Invoke it manually (bypasses the overlap guard):

```bash
PYTHONPATH=../src poetry run brimley invoke reconciler --root . --input '{}'
```

Or start the REPL to see it scheduled automatically:

```bash
PYTHONPATH=../src poetry run brimley repl --root .
```

Then check task status:

```text
brimley > /tasks
brimley > reconciler {}
brimley > /quit
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

You can run MCP tools without REPL using the CLI command:

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
- `di_provider.py`: DI example — `@provider` singleton with yield teardown, `@on_startup` hook, and `@function` with `Depends()` injection (0.8+).
- `github_profile.yaml`: API function — fetches a GitHub user profile via the GitHub REST API (0.7+).
- `system_metrics.yaml`: CLI function — reports system load average via `uptime` with regex result parsing (0.7+).
- `task_reconciler.py`: Managed task function — periodic reconciler declared with `@function(task={...})`; demonstrates `interval`, `immediate`, `retries`, and `retry_interval` parameters (0.9+).
