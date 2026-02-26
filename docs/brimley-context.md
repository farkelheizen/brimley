# Brimley Context

> Version 0.5

The `BrimleyContext` is the central nervous system of a Brimley application.

## The Context Object

```
class BrimleyContext(Entity):
    settings: FrameworkSettings     # Internal Framework Config
    config: AppConfig               # User Application Config
    mcp: MCPSettings                # MCP Runtime Settings
    auto_reload: AutoReloadSettings # Watcher Runtime Settings
    execution: ExecutionSettings    # Runtime Execution Controls
    app: Dict[str, Any]             # Mutable Application State
    
    functions: Registry[BrimleyFunction]
    entities: Registry[Entity]
    databases: Dict[str, Engine]
```

|**Attribute**|**Source (YAML)**|**Mutability**|**Description**|
|---|---|---|---|
|`settings`|`brimley:`|**Read-Only**|Framework settings (env, logging, app name).|
|`config`|`config:`|**Read-Only**|User-defined configuration (API keys, constants).|
|`mcp`|`mcp:`|**Read-Only**|MCP runtime settings (embedded mode, transport, host, port).|
|`auto_reload`|`auto_reload:`|**Read-Only**|Polling watcher settings (enabled, interval/debounce, include/exclude patterns).|
|`execution`|`execution:`|**Read-Only**|Sync execution controls (thread pool size, timeout budget, queue capacity/behavior).|
|`app`|`state:`|**Mutable**|Global shared state. Seeded from YAML, modified at runtime.|
|`functions`|N/A|**Resolved**|Registry of internal Brimley functions.|
|`entities`|N/A|**Resolved**|Registry of domain models.|
|`databases`|`databases:`|**Managed**|Active SQLAlchemy engines.|

## Fields

1. **`settings`**:
    
    - **Type**: `FrameworkSettings`
        
    - **Purpose**: Internal framework configuration loaded from the `brimley` section of `brimley.yaml` (e.g., environment, log level).
        
    - **Access**: `ctx.settings.env`
        
2. **`config`**:
    
    - **Type**: `AppConfig`
        
    - **Purpose**: User-defined application configuration loaded from the `config` section of `brimley.yaml`.
        
    - **Access**: `ctx.config.support_email`

3. **`mcp`**:
    
    - **Type**: `MCPSettings` (or equivalent MCP config model)
        
    - **Purpose**: Runtime MCP behavior loaded from the `mcp` section of `brimley.yaml`.
        
    - **Access**: `ctx.mcp.port`
        
4. **`execution`**:

    - **Type**: `ExecutionSettings`

    - **Purpose**: Runtime execution controls loaded from the `execution` section of `brimley.yaml`.

    - **Access**: `ctx.execution.timeout_seconds`

5. **`app`**:
    
    - **Type**: `Dict[str, Any]`
        
    - **Purpose**: Mutable, application-level state. Seeded from the `state` section of `brimley.yaml`.
        
    - **Access**: `ctx.app["maintenance_mode"]`
        
6. **`auto_reload`**:

    - **Type**: `AutoReloadSettings`

    - **Purpose**: Runtime watch-mode configuration loaded from the `auto_reload` section of `brimley.yaml`.

    - **Access**: `ctx.auto_reload.enabled`

7. **`functions`**:
    
    - **Type**: `Registry[BrimleyFunction]`
        
    - **Purpose**: The lookup table for all executable capabilities available to the system.
        
    - **Access**: `ctx.functions.get("calculate_tax")`

    - **Composition Helper**: `ctx.execute_function_by_name("calculate_tax", {"subtotal": 100})`
        
8. **`entities`**:
    
    - **Type**: `Registry[Entity]`
        
    - **Purpose**: The central repository for all domain models and data schemas.
        
    - **Built-ins**:
        
        - `ContentBlock`
            
        - `PromptMessage`
            
    - **Access**: `ctx.entities.get("UserProfile")`
        
9. **`databases`**:
    
    - **Type**: `Dict[str, Engine]`
        
    - **Purpose**: A registry of active database connection pools (SQLAlchemy engines).
        

## Lifecycle

1. **Initialization**:
    
    - The `BrimleyContext` is instantiated at the entry point of the application (CLI start or Server boot).
        
    - `brimley.yaml` is loaded and interpolated.
        
    - `settings`, `config`, `mcp`, `auto_reload`, `execution`, and `app` (initial state) are populated.
        
    - **Built-in Entities** (`ContentBlock`, `PromptMessage`) are automatically registered in `entities`.
        
2. **Infrastructure Hydration**:

    - Active database connections are established based on the `databases` section in `brimley.yaml`.
    - SQLAlchemy `Engine` objects are created and stored in `ctx.databases`.

3. **Hydration (Discovery)**:
    
    - The **Discovery Engine** scans the file system.
        
    - Found **Functions** are registered into `ctx.functions`.
        
    - Found **Entities** (typically decorated Python classes) are registered into `ctx.entities`.
        
3. **Execution**:
    
    - When a request comes in (or a CLI command is run), the `context` is passed to the dispatcher.
        
    - Functions receive context objects via dependency injection (for example, `BrimleyContext` or `fastmcp.Context` type hints), allowing access to settings, config, state, and runtime services.

    - Dispatcher queue/thread/timeout behavior follows `ctx.execution` settings.

4. **Optional Runtime Reload**:

    - REPL watch mode and host runtime controller read `ctx.auto_reload` to configure polling/debounce behavior.

    - Successful reload cycles may refresh MCP tools; failed cycles keep unaffected runtime domains available.

## Function Composition from Context

`BrimleyContext` includes a convenience method for nested function execution:

```python
ctx.execute_function_by_name(
    function_name="child_function",
    input_data={"name": "Ada"},
)
```

This method delegates to Brimley's standard invocation pipeline (lookup -> argument resolution -> dispatcher execution), so nested calls behave the same way as CLI and REPL invocations.

## Injection Examples

### BrimleyContext injection

```python
from brimley import function
from brimley.core.context import BrimleyContext

@function
def audit_ping(ctx: BrimleyContext) -> dict:
    return {"functions": len(ctx.functions), "env": ctx.settings.env}
```

### fastmcp.Context injection

```python
from brimley import function
from fastmcp.server.context import Context

@function(mcpType="tool")
def sample_with_context(prompt: str, mcp_ctx: Context) -> str:
    sample = mcp_ctx.session.sample(messages=[{"role": "user", "content": prompt}])
    return sample.message.content[0].text
```