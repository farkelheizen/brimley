# Brimley Functions

Brimley functions are the core execution units of the framework. Python functions are defined with decorators, while SQL/template functions use embedded metadata frontmatter.

## Metadata Schema

Function metadata defines the function's name, type, arguments, return shape, and optional MCP exposure settings.

- **Python functions**: metadata comes from `@function(...)` decorators and type hints.
- **SQL/template functions**: metadata comes from frontmatter in source files.

## Core Properties

All functions share core properties.

| **Property**      | **Type**        | **Required** | **Description**                                                                 |
| ----------------- | --------------- | ------------ | ------------------------------------------------------------------------------- |
| `name`            | string          | Yes          | Unique function name. See [naming conventions](brimley-naming-conventions.md). |                                                                               |
| `type`            | string          | Yes          | Indicates the type of function.                                                     |
| `description`     | string          | No           |                                                                                 |
| `arguments`       | dict            | No           | See [arguments](brimley-function-arguments.md). |        
| `return_shape`    | string \| dict  | Yes          | See [return shape](brimley-function-return-shape.md). |                             |
|`mcp`|object|Configuration for exposing the function via Model Context Protocol.|No|


## Types of Functions

| **Function Type** | **File Extension(s)** | **Description** |
| -- | -- | -- |
| [Template Functions](brimley-template-functions.md) | `*.md` (and metadata-backed templates) | Jinja-based prompt/text rendering with argument mapping. |
| [Python Functions](brimley-python-functions.md) | `*.py` | Native Python handlers discovered from `@function` / `@function(...)`. |
| [SQL Functions](brimley-sql-functions.md) | `*.sql` | Parameterized SQL execution with metadata frontmatter. |
| [API Functions](brimley-api-functions.md) | `*.yaml` | Declarative HTTP integrations via `httpx`. Introduced in 0.7. |
| [CLI Functions](brimley-cli-functions.md) | `*.yaml` | Declarative subprocess execution via `asyncio.create_subprocess_exec`. Introduced in 0.7. |

### Task Functions *(Introduced in 0.9)*

Task functions are Python functions that include scheduling metadata via `@function(task={...})`. They are not a separate function type — they use the same `python_function` type in the registry and are discovered, dispatched, and injected like any other Python function.

The `task` dict tells the `TaskScheduler` how to run the function periodically:

```python
from brimley import function, BrimleyContext

@function(name="reconciler", task={"interval": "5m", "immediate": True})
async def reconciler(ctx: BrimleyContext) -> dict:
    ...
```

Key distinctions:
- Task functions **must be async** and **must not be MCP tools** (`mcpType` cannot be set alongside `task`).
- Parameters are limited to `BrimleyContext` and `Depends()` injections — no user-facing arguments.
- The `TaskScheduler` runs task functions on a dedicated daemon thread in `repl` and `mcp-serve` modes. In `invoke` mode, the function is available for one-shot invocation but the scheduler does not run.
- Scheduling metadata (`interval`, `immediate`, `retries`, `retry_interval`) is immutable across hot reload; a restart is required to change the schedule.

See [Python Functions — Section 9](brimley-python-functions.md) for full parameter reference and quarantine rules.

### The `mcp` Block

The `mcp` block marks a function as eligible for MCP tool export via FastMCP.

For Python functions, the equivalent is typically `@function(mcpType="tool")`.

```
mcp:
  type: tool
  # Optional: overrides the main description specifically for the LLM
  description: "Use this tool to calculate user metrics. Do not pass PII."
```

_(See_ [_MCP Integration_](brimley-model-context-protocol-integration.md "null") _for more details on argument filtering and MCP server behavior)._

## Example Definition

```
---
name: hello_world
type: template_function
description: "Greets the user and provides support contact info."
arguments:
  inline:
    name:
      type: string
      default: "World"
  support_email:
    type: string
    from_context: "config.support_email"
mcp:
  type: tool
---

# Hello {{ args.name }}!
Welcome to Brimley.
Contact us at: {{ args.support_email }}
```