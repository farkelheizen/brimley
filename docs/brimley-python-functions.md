# Brimley Python Functions

> Version 0.3

Python Functions are native Python callables registered with the `@function` decorator. In Brimley 0.3, this is the primary Python discovery model.

## 1. Decorator-Based Registration

Use `@function` directly on your handler:

```python
from brimley import function

@function
def ping() -> str:
    return "pong"
```

You can also provide options:

```python
from brimley import function

@function(name="summarize", mcpType="tool", reload=True)
def summarize(text: str) -> str:
    return text[:120]
```

Both forms are supported:

- `@function`
- `@function(...)`

## 2. Decorator Options

| Option | Type | Default | Description |
|---|---|---|---|
| `name` | `str \| None` | inferred from function name | Public function name in registry. |
| `type` | `str` | `python_function` | Function kind. For Python handlers this should remain `python_function`. |
| `reload` | `bool` | `True` | Controls whether this function participates in hot reload module rehydration. |
| `mcpType` | `str \| None` | `None` | Set to `"tool"` to expose the function as an MCP tool. |
| `**kwargs` | `Any` | n/a | Reserved extension metadata. |

## 3. Discovery and Handler Resolution

During static discovery, Brimley parses Python modules with AST (`ast.parse`) and identifies decorated functions without importing/executing user code.

For each discovered Python function, Brimley derives:

- `name` from decorator `name` or function definition name
- `handler` as `{module_name}.{function_name}`
- `description` from docstring
- `arguments` from signature and annotations
- `return_shape` from return annotation

Legacy YAML-frontmatter Python parsing may still be supported during transition, but decorator-based registration is the canonical 0.3 path.

## 4. `reload=True/False` Behavior

`reload` controls participation in auto-reload rehydration:

- `reload=True` (default): function is eligible for module re-import/rehydration during hot reload.
- `reload=False`: function is excluded from rehydrate updates and keeps previous loaded behavior until full reload/restart.

When a module mixes reload policies, Brimley applies conservative policy to maintain runtime safety.

## 5. MCP Tool Exposure (`mcpType="tool"`)

Set `mcpType="tool"` to mark a Python function for MCP tool registration:

```python
from brimley import function

@function(mcpType="tool")
def get_status(service: str) -> dict:
    return {"service": service, "status": "ok"}
```

Brimley maps this to MCP metadata (`type: tool`) during discovery/registration.

## 6. Dependency Injection and `Annotated`

Python function arguments are inferred from signatures. Brimley supports both user inputs and injected parameters.

### A. App/Config injection with `Annotated`

```python
from typing import Annotated
from brimley import function, AppState, Config

@function
def health(
    env: Annotated[str, Config("env")],
    start_time: Annotated[float, AppState("start_time")],
) -> dict:
    return {"env": env, "start_time": start_time}
```

These map to `from_context` entries during argument inference.

### B. Context-type injection (system parameters)

Brimley treats the following typed parameters as injected/system arguments:

- `BrimleyContext`
- `Context` (FastMCP context aliases)
- `MockMCPContext` (test/runtime compatibility)

System-injected parameters are excluded from public argument schema and provided by runtime injections.

### C. Composing functions via context

```python
from brimley import function
from brimley.core.context import BrimleyContext

@function
def orchestrate(user_id: int, ctx: BrimleyContext) -> dict:
    profile = ctx.execute_function_by_name("get_user_profile", {"user_id": user_id})
    return {"user_id": user_id, "profile": profile}
```

## 7. Return Shape Inference

Return annotations are mapped to Brimley return shapes.

Examples:

- `-> str` → `string`
- `-> int` → `int`
- `-> list[dict]` / `-> List[dict]` → `dict[]`
- `-> None` → `void`
- `-> User` → `User`

See [Return Shapes](brimley-function-return-shape.md) for full mapping and validation behavior.