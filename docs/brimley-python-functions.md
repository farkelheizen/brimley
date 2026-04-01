# Brimley Python Functions
> Docs baseline: 0.9.x

Python Functions are native Python callables registered with the `@function` decorator. This is the primary Python discovery model.

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
| `task` | `dict \| None` | `None` | Scheduling metadata. When present, the function is registered as a managed task. See [Section 9](#9-managed-tasks-task) below. |
| `**kwargs` | `Any` | n/a | Reserved extension metadata. |

## 3. Discovery and Handler Resolution

During static discovery, Brimley parses Python modules with AST (`ast.parse`) and identifies decorated functions without importing/executing user code.

For each discovered Python function, Brimley derives:

- `name` from decorator `name` or function definition name
- `handler` as `{module_name}.{function_name}`
- `description` from docstring
- `arguments` from signature and annotations
- `return_shape` from return annotation

Legacy YAML-frontmatter Python parsing is removed; decorator-based registration is required.

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

## 7. Provider Injection with `Depends()` *(0.8+)*

`Depends()` is the preferred way to inject DI-managed dependencies into `@function`-decorated callables. It is used as a parameter default value — the container resolves the named provider at execution time and injects the resolved object as the argument value.

```python
from brimley import function, Depends

@function
def greet(name: str, counter=Depends("request_counter")) -> str:
    counter.increment()
    return f"Hello, {name}! (call #{counter.value})"
```

### Rules

- The argument to `Depends()` is the provider name (a string matching a `@provider`-decorated function's name or its `name=` override).
- `Depends` parameters are **invisible to external callers** — they are excluded from CLI/REPL/MCP argument schemas. Do not expose provider state through user-facing schemas.
- If no container is set on the context (e.g., tests without DI), a `BrimleyExecutionError` is raised. Use `container.override()` or supply a request-scoped context in tests.
- If the named provider is not registered, a `BrimleyExecutionError` is raised with a clear message.
- Caller-supplied values for a `Depends` parameter take precedence over the container resolution (useful in testing).

### Injection in `BrimleyContext`-typed Parameters

Providers may also declare a `ctx: BrimleyContext` parameter; the container injects the current context automatically. This is handled at the provider-resolution level, not via `Depends()`.

```python
from brimley import provider, BrimleyContext

@provider(scope="singleton")
def get_app_name(ctx: BrimleyContext) -> str:
    return ctx.settings.app_name
```

## 8. Return Shape Inference

Return annotations are mapped to Brimley return shapes.

Examples:

- `-> str` → `string`
- `-> int` → `int`
- `-> list[dict]` / `-> List[dict]` → `dict[]`
- `-> None` → `void`
- `-> User` → `User`

See [Return Shapes](brimley-function-return-shape.md) for full mapping and validation behavior.

## 9. Managed Tasks (`task={...}`) *(0.9+)*

A Python function can be declared as a **managed task** by passing a `task` dict to `@function`. The `TaskScheduler` picks up all task functions during startup and runs them periodically in a dedicated daemon thread with its own asyncio event loop.

```python
from brimley import function, BrimleyContext

@function(
    name="health_check",
    task={
        "interval": "1m",
        "immediate": True,
        "retries": 2,
        "retry_interval": "10s exponential",
    },
)
async def health_check(ctx: BrimleyContext) -> dict:
    """Periodic health-check task."""
    return {"status": "ok"}
```

### Task Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `interval` | string | Yes | How often to run. Human-readable: `"30s"`, `"5m"`, `"1h 30m"`. Minimum: 5 seconds. |
| `immediate` | bool | No (default `False`) | If `True`, run once immediately at scheduler start before the first interval elapses. |
| `retries` | int | No (default `0`) | How many times to retry the function after an exception before giving up. |
| `retry_interval` | string | No (default `"5s fixed"`) | Backoff between retries. Formats: `"10s fixed"`, `"5s exponential"`, `"3s multiplier:2.0"`. |

### Retry Interval Formats

- **`"N unit fixed"`**: constant wait between retries. Example: `"10s fixed"`.
- **`"N unit exponential"`**: doubles on each retry up to a ceiling of `interval`. Example: `"5s exponential"` → 5s, 10s, 20s, … capped at `interval`.
- **`"N unit multiplier:X"`**: multiplies by `X` on each retry up to a ceiling of `interval`. Example: `"3s multiplier:2.5"`.

### Scanner Quarantine Rules

The Scanner validates task functions during discovery. Violations produce a warning diagnostic and **skip** the function (the server continues to boot):

1. **MCP prohibition**: A function with `task` set must not also have `mcpType` set. Task functions are not exposed as MCP tools.
2. **Signature constraint**: Task function parameters must be limited to `BrimleyContext` and `Depends()` injections. No user-facing arguments.
3. **Async validation**: Task functions must be declared `async def`.
4. **Interval minimum**: `interval` must parse to ≥ 5 seconds.

### Scheduling Behavior

- The `TaskScheduler` starts only in `repl` and `mcp-serve` modes. In `invoke` mode, the scheduler is instantiated but not started — `brimley invoke <task_name>` executes the function once without scheduling semantics.
- The overlap guard prevents a new scheduled run from starting if the previous run is still executing. Manual invocation via `brimley invoke` or the REPL bypasses the overlap guard.
- Scheduling metadata (`interval`, `immediate`, `retries`, `retry_interval`) is immutable across hot reload. Only the function body is refreshed. A restart is required to apply schedule changes. The REPL emits a `WARN_TASK_SCHEDULE_CHANGED` diagnostic when reloaded metadata diverges from the running schedule.
- Use `/tasks` in the REPL to inspect task names, scheduling state, failure counts, and next run times.