# Brimley Python Functions

> Version 0.2

Python Functions in Brimley allow developers to execute complex logic, perform data transformations, and interact with external systems using native Python code. These functions benefit from **Reflection-Driven Schema Generation** and **Dependency Injection**.

## 1. Core Properties

| **Property**   | **Type** | **Required** | **Description**                                                         |
| -------------- | -------- | ------------ | ----------------------------------------------------------------------- |
| `name` | string | Yes | The unique identifier for the function. |
| `type` | string | Yes | Always `python_function`. |
| `handler` | string | Conditional | The dot-notation path to the Python function (e.g., `pkg.module.func`). |
| `description` | string | No | A docstring or explicit description for LLM discovery. |
| `arguments` | dict | No | Inferred via reflection by default; can be overridden. | 
| `return_shape` | dict | No | Defines the output structure. |

## 2. Registration Methods

### A. The `@brimley_function` Decorator

The most common way to define a function is within Python code. When a function is decorated, the `handler` is **inferred**automatically by the framework.

```
from typing import List, Annotated
from brimley import brimley_function, Connection

@brimley_function(name="process_batch")
def process_batch(
    ids: List[int],
    # Dependency Injection: Inject the 'default' database connection
    db: Annotated[Connection, "default"]
):
    """Processes a batch of record IDs."""
    # ... logic using db ...
    return {"count": len(ids)}

```

### B. YAML Definition

You can register existing Python functions (or third-party library functions) via a `.yaml` file. In this mode, the `handler` is **required** to serve as a pointer to the code.

```
name: calculate_risk
type: python_function
handler: analytics_engine.risk.calculate
description: "Calculates risk score for a specific profile"
arguments:
  inline:
    profile_id: int
    strict_mode: bool

```

## 3. The `handler` Property

The `handler` string represents the fully qualified name of the Python function.

- **Inference:** When using the decorator, Brimley captures the module and function name at runtime.
    
- **Explicit Mapping:** In YAML, the handler must be importable by the Brimley runner.
    

## 4. Dependency Injection

Brimley Functions are designed to be "Pure." You do not receive a massive `context` object. Instead, you declare the specific resources you need using Python Type Annotations.

### A. Database Connections

To get a database connection, use the `Connection` type hint combined with `Annotated` to specify the pool name.

```
from typing import Annotated
from brimley import Connection

# Injects the connection named 'warehouse' defined in context.databases
def list_products(db: Annotated[Connection, "warehouse"], category: str):
    return db.fetch_all("SELECT * FROM items WHERE category = :c", {"c": category})

```

### B. App State & Config

You can inject specific values from the global state using `AppState` and `Config` markers.

```
from typing import Annotated
from brimley import AppState, Config
import time

def health_check(
    # Injects context.app["start_time"]
    start_time: Annotated[float, AppState("start_time")],
    # Injects context.config.env
    env: Annotated[str, Config("env")]
):
    return {"uptime": time.time() - start_time, "env": env}

```

### C. BrimleyContext Injection

For internal composition and advanced runtime behaviors, Python handlers may request the full `BrimleyContext` by type hint.

```python
from brimley.core.context import BrimleyContext

def orchestrate(task: str, ctx: BrimleyContext):
    ctx.app["last_task"] = task
    return {"task": task, "registered_functions": len(ctx.functions)}
```

When `BrimleyContext` is type-hinted in the function signature, Brimley injects the active runtime context automatically.

### D. MCP Context Injection (Agentic Sampling)

Agentic Python handlers can opt-in to receiving FastMCP runtime context with `mcp.server.fastmcp.Context`.

```python
from mcp.server.fastmcp import Context

def summarize_with_model(prompt: str, mcp_ctx: Context):
    sample = mcp_ctx.session.sample(messages=[{"role": "user", "content": prompt}])
    return sample.message.content[0].text
```

During MCP tool execution, Brimley forwards FastMCP `ctx` into runtime injections so the Python runner can inject this dependency by type hint.

## 5. Reflection & Type Mapping

Brimley maps standard Python type hints to JSON Schema types to facilitate tool-calling.

|**Python Type**|**JSON Schema Equivalent**|**Note**|
|---|---|---|
|`int`|`integer`||
|`float` / `Decimal`|`number`||
|`bool`|`boolean`||
|`str`|`string`||
|`List[T]`|`array`|See [collection support](brimley-function-arguments.md#collection-support)|
|`Optional[T]`|`T`|Property is marked as "not required"|
|`Enum`|`string`|Uses the Enum members as `enum` values|

### System Argument Filtering

For MCP-facing schemas, Brimley hides system-injected arguments so external callers only see business inputs.

- `BrimleyContext`-typed parameters are excluded from discovered/public argument schema.
- `mcp.server.fastmcp.Context`-typed parameters are excluded from discovered/public argument schema.
- User-supplied arguments remain visible and validated as normal.