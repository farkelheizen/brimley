# Brimley

Application server for function-based AI tooling, focused on faster iteration loops.

> Status: Brimley is not yet ready for production use. It is aimed at improving the MCP development workflow and is still under active development.

Brimley is an application server that discovers, validates, and executes function-based AI tooling. It owns its own process and event loop, providing three operating modes: an interactive **REPL** for development, a headless **MCP server** for production, and a one-shot **invoke** mode for scripting and CI. The core focus is reducing the change/test loop during MCP tool development: change code → reload → re-test.

## Design goals

- **Faster iteration loop:** author tools in `.py`, `.sql`, `.md`, and `.yaml` files and execute them immediately, without a full redeploy cycle.
- **Safer change workflow:** discovery is AST-first for Python (no import-time execution during scan), with diagnostics instead of immediate process termination.
- **Live runtime ergonomics:** use a thin REPL client attached to a daemon-owned runtime, with optional watch-mode reload.
- **MCP integration path:** expose selected functions as MCP tools via FastMCP when needed.
- **Declarative HTTP and CLI integration (0.7+):** wrap external APIs and shell commands as first-class Brimley functions using YAML — no boilerplate code required.
- **Managed dependency injection (0.8+):** `@provider`, `Depends()`, `@on_startup`/`@on_shutdown` hooks, and `BrimleyContainer` with singleton and request scopes — shared resources with proper lifecycle semantics.
- **Application server ownership (0.9+):** Brimley owns its process and event loop. No embedding inside other Python applications — integrate externally via MCP.
- **Operations clarity:** built-in reload diagnostics, runtime error surfacing, and explicit daemon lifecycle controls.

## Architectural approach

Brimley is an **application server** — it always owns its process and event loop. It separates **tool authoring/execution semantics** from **MCP transport hosting**:

- Brimley handles discovery, schemas, argument resolution, execution, reload policy, and diagnostics.
- FastMCP (optional) handles MCP server transport.

Keeping function logic separate from transport makes it reusable across all three operating modes:

| Mode | Command | Purpose |
|---|---|---|
| **REPL** | `brimley repl` | Interactive development with hot-reload, admin commands, and optional embedded MCP. |
| **MCP Server** | `brimley mcp-serve` | Headless production mode — serves tools over SSE/stdio. |
| **Invoke** | `brimley invoke <name>` | One-shot function execution for scripting, CI, and debugging. No background services are started. |

> **Note:** Embedding Brimley as a library inside another Python application (e.g., importing into FastAPI) is not supported. External applications integrate with Brimley via MCP as a sidecar process.

## Quick Start

### 1) Install

```bash
poetry install
```

Optional MCP support:

```bash
poetry install -E fastmcp
```

Optional Oracle SQL support:

```bash
poetry install -E oracle
```

This is only needed if you want Brimley SQL tools to connect to Oracle.

### 2) Add `brimley.yaml`

```yaml
brimley:
  app_name: "Brimley App"

config:
  support_email: "support@example.com"

state:
  request_count: 0

databases:
  default:
    url: "sqlite:///./data.db"

auto_reload:
  enabled: true

mcp:
  host: 127.0.0.1
  port: 8000
```

### 3) Add a Python function (`calc.py`)

```python
from brimley import function

@function(mcpType="tool")
def calculate_tax(amount: float, rate: float = 8.25) -> float:
    return round(amount * (rate / 100.0), 2)
```

### 4) Run REPL

```bash
PYTHONPATH=src poetry run brimley repl --root .
```

### 5) Invoke once from CLI

```bash
PYTHONPATH=src poetry run brimley invoke calculate_tax --root . --input "{amount: 100, rate: 8.25}"
```

## Optional Oracle SQL Tools

Brimley's SQL tools execute against SQLAlchemy `Engine` objects. For Oracle, that means Brimley needs:

- the Oracle driver installed (`poetry install -E oracle`, which installs `oracledb`)
- an Oracle SQLAlchemy URL such as `oracle+oracledb://user:pass@dbhost:1521/?service_name=FREEPDB1`
- any pool settings you want under `databases.<name>` in `brimley.yaml`

Example:

```yaml
databases:
  oracle:
    url: ${ORACLE_URL}
    pool_size: 5
    max_overflow: 10
    pool_pre_ping: true
    pool_recycle: 1800
    connect_args:
      stmtcachesize: 50
```

Any SQL function with `connection: oracle` will use that pooled engine. Brimley forwards SQLAlchemy engine options from the database config block directly to `create_engine(...)`, except for `url` and the legacy `connector` metadata key.

If you want a complete optional Oracle walkthrough, including Docker startup and a startup-hook-created demo schema, use the isolated example in `oracle_examples/README.md`. The baseline `examples/` directory remains SQLite-first.

## Core CLI Commands

- `brimley repl --root . [--mcp|--no-mcp] [--watch|--no-watch]`
- `brimley repl --root . --shutdown-daemon`
- `brimley mcp-serve --root . [--watch|--no-watch] [--host HOST] [--port PORT]`
- `brimley invoke <function_name> --root . --input "{...}"`
- `brimley build --root . [--output PATH]`
- `brimley validate --root . [--format text|json] [--fail-on warning|error] [--output PATH]`
- `brimley schema-convert --in schema.yaml --out fieldspec.yaml [--allow-lossy]`

## MCP Integration

Mark a function as an MCP tool:

- Python: `@function(mcpType="tool")`
- SQL/Template/API/CLI frontmatter: 

```yaml
mcp:
  type: tool
```

API and CLI functions defined in `.yaml` files are first-class MCP tools. See [API Functions](docs/brimley-api-functions.md) and [CLI Functions](docs/brimley-cli-functions.md).

Then serve tools with:

```bash
PYTHONPATH=src poetry run brimley mcp-serve --root .
```

## Runtime Model (0.9 architecture baseline)

Brimley is an application server that owns its process and event loop. It does not support being embedded as a library inside another Python application.

- **REPL mode:** Thin client attached to a daemon-owned runtime. Daemon owns state, watcher lifecycle, and optional embedded MCP hosting.
- **MCP server mode:** Headless process serving tools over SSE/stdio via FastMCP.
- **Invoke mode:** One-shot function execution — no daemon, no background services, no task scheduler.
- `/detach` leaves daemon running; `/quit` (or `--shutdown-daemon`) terminates daemon session.
- Reload is partitioned and diagnostics-driven; schema-shape tool changes require MCP client reconnect.

## Documentation Map

- [High-level design](docs/brimley-high-level-design.md)
- [CLI & REPL harness](docs/brimley-cli-and-repl-harness.md)
- [Configuration](docs/brimley-configuration.md)
- [Discovery & loader spec](docs/brimley-discovery-and-loader-specification.md)
- [MCP integration](docs/brimley-model-context-protocol-integration.md)
- [SQLite-first baseline examples](examples/README.md)
- [Optional Oracle example](oracle_examples/README.md)
- [API Functions](docs/brimley-api-functions.md) *(0.7+)*
- [CLI Functions](docs/brimley-cli-functions.md) *(0.7+)*
- [Secrets](docs/brimley-secrets.md) *(0.7+)*
- [Security — Threat Model](docs/security/brimley-0.7-threat-model.md) *(0.7+)*
- [Dependency Injection & Managed Objects](docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md) *(0.8+)*
- [Application Server Boundary & Managed Tasks](docs/roadmap/brimley-0.9-application-server-and-managed-tasks.md) *(0.9+)*
