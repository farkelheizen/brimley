# Brimley

Experimental MCP tooling runtime for testing faster iteration loops.

> Status: Brimley is currently experimental and not ready for production use. This project is intended to prove out a faster MCP development workflow, not to provide a hardened production platform.

Brimley is an authoring and execution engine for function-based AI tooling. It is focused on reducing the change/test loop during MCP tool development: change code -> reload -> re-test.

## Why teams use Brimley

- **Faster iteration loop:** author tools in `.py`, `.sql`, and `.md` files and execute them immediately.
- **Safer change workflow:** discovery is AST-first for Python (no import-time execution during scan), with diagnostics instead of immediate process termination.
- **Live runtime ergonomics:** use a thin REPL client attached to a daemon-owned runtime, with optional watch-mode reload.
- **MCP integration path:** expose selected functions as MCP tools via FastMCP when needed.
- **Operations clarity:** built-in reload diagnostics, runtime error surfacing, and explicit daemon lifecycle controls.

In short: Brimley is an experiment aimed at shortening feedback loops while MCP tooling behavior is still being developed.

## What makes Brimley different

Brimley separates **tool authoring/execution semantics** from **MCP transport hosting**:

- Brimley handles discovery, schemas, argument resolution, execution, reload policy, and diagnostics.
- FastMCP (optional) handles MCP server transport.

This keeps function logic reusable across local REPL workflows, dedicated MCP serving, and host-embedded deployments.

## Quick Start

### 1) Install

```bash
poetry install
```

Optional MCP support:

```bash
poetry install -E fastmcp
```

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
    connector: sqlite
    url: "sqlite:///./data.db"

auto_reload:
  enabled: true

mcp:
  embedded: true
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
- SQL/Template frontmatter: 

```yaml
mcp:
  type: tool
```

Then serve tools with:

```bash
PYTHONPATH=src poetry run brimley mcp-serve --root .
```

## Runtime Model (0.5 architecture baseline)

- REPL uses a **thin client** attached to a daemon-owned runtime.
- Daemon owns state, watcher lifecycle, and embedded MCP hosting.
- `/detach` leaves daemon running; `/quit` (or `--shutdown-daemon`) terminates daemon session.
- Reload is partitioned and diagnostics-driven; schema-shape tool changes require MCP client reconnect.

## Documentation Map

- [High-level design](docs/brimley-high-level-design.md)
- [CLI & REPL harness](docs/brimley-cli-and-repl-harness.md)
- [Configuration](docs/brimley-configuration.md)
- [Discovery & loader spec](docs/brimley-discovery-and-loader-specification.md)
- [MCP integration](docs/brimley-model-context-protocol-integration.md)


