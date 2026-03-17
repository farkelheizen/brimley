# Brimley 0.8: Dependency Injection & Managed Objects

> **ADR Reference:** [ADR-0001](../decisions/0001-swap-di-and-mocking-order.md) — DI precedes Mocking so that the Mocking framework can integrate via `BrimleyContainer.override()` rather than building a redundant standalone registry.

## Overview

Brimley 0.8 introduces a lightweight, **custom** Dependency Injection system. It is deliberately minimal in scope and built from scratch to work within Brimley's AST-scanning architecture.

### Why a Custom DI System?

Brimley discovers Python functions via **zero-execution AST scanning** — it parses files with `ast.parse()` without importing or running user modules. Off-the-shelf DI libraries (`dependency-injector`, `injector`, `wireup`, etc.) require importing the container module and executing provider factory functions to wire up the dependency graph. This is fundamentally incompatible with the scanner model.

**`BrimleyContainer` uses a two-phase design:**

1. **Scan phase (AST, no imports):** The `@provider` decorator is detected via AST. The scanner records provider metadata (name, scope, module path, function signature) into the Registry — nothing is constructed or imported.
2. **Startup phase (after import):** `BrimleyContainer` imports provider modules and constructs singletons. Request-scoped providers are constructed per `Dispatcher.run()` call.

This mirrors the existing `@function` and `@entity` two-phase discovery pattern. Providers are simply another type of registered artifact.

### Intentionally Minimal Scope

v0.8 DI is not a general-purpose injection framework. Only the following patterns are in scope:

**In scope:**
- `@provider(scope="singleton")` — constructed once at startup, shared globally
- `@provider(scope="request")` — constructed per `Dispatcher.run()` call
- `Depends()` — inject a provider's value into a `@function` argument
- `@on_startup` — run a callable after all singletons are initialized
- `@on_shutdown` — run a callable on graceful shutdown

**Explicitly out of scope:**
- Named/qualified bindings and multibindings
- Interceptors or middleware hooks
- Circular dependency resolution
- Property injection
- Hierarchical containers / child scopes
- Any XML, annotation, or config-file-based wiring

This covers 100% of the known v0.8 use cases: managed DB pools, `httpx.AsyncClient` singletons, `SecretProvider` credential sources, and startup/shutdown lifecycle hooks.

## 1. The Managed Container

Brimley maintains a central `BrimleyContainer` that manages the lifecycle of dependencies.

### Scopes:

- **`singleton` (Global):** Created once at startup (e.g., a Database Pool, an OpenAI Client).
    
- **`request` (Transient):** Created fresh for every `Dispatcher.run()` call (e.g., an Auth Context, a Transaction handle).
    

## 2. Defining Providers

Dependencies are defined using the `@brimley.provider` decorator. These can be located in any Python file scanned by Brimley.

```
from brimley import provider
import httpx

@provider(scope="singleton")
def get_http_client():
    # Setup logic
    client = httpx.AsyncClient()
    yield client
    # Teardown logic
    client.close()
```

## 3. Injecting Dependencies

Brimley uses the `Depends` pattern for injecting these objects into your functions.

```
from brimley import function, Depends

@function(name="fetch_secure_data")
async def fetch_secure_data(
    url: str, 
    client: httpx.AsyncClient = Depends(get_http_client)
):
    response = await client.get(url)
    return response.json()
```

## 4. Named Dependencies

> **Out of scope for v0.8.** Named/qualified bindings are explicitly deferred (see Minimal Scope above). All providers in v0.8 are identified by their Python function reference passed to `Depends()`. Named string-based injection is not supported.

## 5. Lifecycle Management: Startup & Shutdown

Because Brimley scans files without fully executing them, you must use explicit hooks for startup tasks. **Lifecycle hooks are fully dependency-injection aware.**

### A. The `@on_startup` Hook

Logic that must run before the application begins accepting requests. You can inject the `BrimleyContext` or any other registered provider.

```
from brimley import on_startup, BrimleyContext, Depends

@on_startup
async def initialize_database(ctx: BrimleyContext):
    # Access app configuration via context
    db_url = ctx.app.config.get("db_url")
    print(f"Initializing Database schema for {ctx.app_id}...")
    await my_db_init_logic(db_url)
```

### B. The `@on_shutdown` Hook

Logic for graceful cleanup when the Brimley process is terminated.

### C. Eager vs. Lazy Providers

By default, providers are **Lazy**. Set `eager=True` to force initialization during the Startup phase.

## 6. Internal Refactor: SQL Connection Provider

The `SqlRunner` is refactored to depend on a managed provider named `db_connection`. This provider is usually marked as `eager=False` to keep startup instantaneous unless a SQL function is actually called.

## 7. Key Integration Points

### A. Context-Aware Injection

Dependencies can depend on other dependencies or the current `BrimleyContext`.

### B. Dependency Overriding (Mocking — v0.9)

`BrimleyContainer` exposes an `override()` API that the v0.9 Mocking framework consumes:

```python
container.override(provider_name, mock_impl)
```

The original standalone `MockRegistry` pattern from the v0.7 draft (parallel registry, Dispatcher-level intercept) is **abandoned**. The v0.9 Mocking spec is written from scratch on this interface. `@brimley.mock` becomes syntactic sugar for registering a test-scoped override. The `container.override()` method must be exposed in v0.8 — even though the Mocking framework is not yet built — so that v0.9 has a stable seam to integrate against.

### C. SecretProvider: Activating the `provider` Secret Source

API and CLI functions defined in v0.7 may declare `provider` sources in their `secrets:` block (see [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md)). In v0.7 these sources raise `BrimleySecretResolutionError` at startup. In v0.8, `BrimleyContainer` activates them:

```yaml
secrets:
  api_key:
    - env: MY_API_KEY        # v0.7: tried first
    - provider: api_creds    # v0.8+: now functional
```

The runner resolution logic calls `container.resolve(provider_name)` when it encounters a `provider:` source. No YAML changes are required in functions written for v0.7.

## 8. Implementation Strategy

### The Startup Sequence

1. **Scan (AST, no imports):** The `Scanner` builds the `Registry`. `@provider` decorators are detected via AST; metadata (name, scope, module path, signature) is recorded without importing or constructing anything.
2. **Import:** `BrimleyContainer` imports provider modules.
3. **Eager Load:** All `@provider(eager=True)` instances are constructed and yielded.
4. **Startup Hooks:** All `@on_startup` callables are awaited in declaration order. Arguments are resolved via the `DependencyResolver`.
5. **Ready:** The application begins accepting requests. Lazy `singleton` providers are constructed on first `Depends()` resolution. `request`-scoped providers are constructed per `Dispatcher.run()` call.
    

## 9. Error Handling & Fail-Fast Policy

Brimley 0.8 enforces a strict "Fail-Fast" policy for the startup sequence to ensure environment integrity.

- **Aborting Startup:** If any `@on_startup` hook or `eager=True` provider raises an unhandled exception, the startup sequence is immediately aborted.
    
- **Protocol Impact:**
    
    - **MCP:** The server will **not** send the "Ready" signal to the host (e.g., Claude Desktop), preventing the host from attempting to call tools that may be in a broken state.
        
    - **REPL/CLI:** The process will exit with a non-zero status code after logging the traceback to `stderr`.
        
- **Diagnostic Logging:** Errors are logged using `loguru` with a specific `system_boot` correlation ID, making it easy to filter for initialization failures in multi-sink logs.
    
- **Cleanup:** If a failure occurs after some hooks have already completed, Brimley will attempt to run all registered `@on_shutdown` hooks and provider teardowns (yield blocks) before exiting.