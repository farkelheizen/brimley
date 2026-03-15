# Brimley 0.8: Dependency Injection & Managed Objects

## Overview

Brimley 0.8 introduces a lightweight Dependency Injection (DI) system inspired by Spring (Java) and FastAPI (Python). This system allows developers to define managed objects ("Providers") that can be injected into Python functions, ensuring decoupled logic and easy testability.

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

## 4. Named Dependencies (Multiple Instances)

For cases where you need multiple instances of the same type, you can use the `name` attribute in the provider and inject via `Depends("name")`.

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

### B. Dependency Overriding (Mocking)

The `MockRegistry` is integrated into the DI system. In `brimley test`, you can override a production provider with a mock version.

## 8. Implementation Strategy

### The Startup Sequence

1. **Scan:** The `Scanner` builds the `Registry` (AST-only).
    
2. **Register:** Providers and Hooks are identified.
    
3. **Initialize Hooks:** All `@on_startup` functions are awaited. Arguments are resolved via the `DependencyResolver`.
    
4. **Eager Load:** All `@provider(eager=True)` instances are created.
    
5. **Ready:** The application begins listening for commands/requests.
    

## 9. Error Handling & Fail-Fast Policy

Brimley 0.8 enforces a strict "Fail-Fast" policy for the startup sequence to ensure environment integrity.

- **Aborting Startup:** If any `@on_startup` hook or `eager=True` provider raises an unhandled exception, the startup sequence is immediately aborted.
    
- **Protocol Impact:**
    
    - **MCP:** The server will **not** send the "Ready" signal to the host (e.g., Claude Desktop), preventing the host from attempting to call tools that may be in a broken state.
        
    - **REPL/CLI:** The process will exit with a non-zero status code after logging the traceback to `stderr`.
        
- **Diagnostic Logging:** Errors are logged using `loguru` with a specific `system_boot` correlation ID, making it easy to filter for initialization failures in multi-sink logs.
    
- **Cleanup:** If a failure occurs after some hooks have already completed, Brimley will attempt to run all registered `@on_shutdown` hooks and provider teardowns (yield blocks) before exiting.