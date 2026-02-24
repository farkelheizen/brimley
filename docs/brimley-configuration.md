# Brimley Configuration

> Version 0.4

Brimley applications are configured via a single YAML file (`brimley.yaml`) located in the project root.

## 1. The Configuration File: `brimley.yaml`

The configuration file is divided into seven sections, mapping directly to the Context:

1. **`brimley`**: Framework-level settings (maps to `ctx.settings`).
    
2. **`config`**: User-defined application configuration (maps to `ctx.config`).
    
3. **`state`**: Initial seed data for application state (maps to `ctx.app`).
    
4. **`databases`**: Definitions for SQL connections (hydrates `ctx.databases`).

5. **`mcp`**: MCP runtime settings (mapped to MCP runtime configuration in the application context/runtime).

6. **`auto_reload`**: Watch-mode settings for polling interval, debounce, and file filters.

7. **`execution`**: Runtime execution controls for sync dispatch concurrency, timeouts, and queue behavior.
    

### Example

```
# brimley.yaml

# 1. Framework Settings (Immutable)
brimley:
  env: ${BRIMLEY_ENV:development}
  app_name: "My Customer Portal"
  log_level: "INFO"

# 2. Application Config (Immutable)
# Renamed from 'app' to 'config' to match ctx.config
config:
  support_email: "help@example.com"
  openai_api_key: ${OPENAI_API_KEY}
  feature_flags:
    enable_beta: ${ENABLE_BETA:false}

# 3. Initial Application State (Mutable)
# Seeds the ctx.app dictionary
state:
  maintenance_mode: false
  global_counter: 0
  system_notice: null

# 4. Database Definitions
databases:
  default:
    connector: postgresql
    url: ${DATABASE_URL}
    pool_size: 5

# 5. Model Context Protocol Integration
mcp:
  embedded: true            # Set to false to skip embedded server startup in REPL
  transport: "sse"          # 'sse' (HTTP) or 'stdio'. The REPL forces 'sse' to prevent conflicts.
  host: "127.0.0.1"         # Bind address for the SSE server
  port: 8000                # Port for the SSE server

# 6. Auto Reload (Watch Mode)
auto_reload:
  enabled: false            # Enable watcher in REPL/host runtime when true
  interval_ms: 1000         # Polling interval (min 100)
  debounce_ms: 300          # Debounce window to collapse rapid changes
  include_patterns:         # Tracked files (glob patterns)
    - "*.py"
    - "*.sql"
    - "*.md"
    - "*.yaml"
  exclude_patterns: []      # Optional ignored paths/patterns

# 7. Execution Runtime Controls
execution:
  thread_pool_size: 8       # Max worker threads for synchronous execution
  timeout_seconds: 30.0     # Global timeout budget per invocation
  queue:
    max_size: 128           # Max queued invocations when workers are busy
    on_full: reject         # 'reject' (default) or 'block'
```

## 2. Environment Variable Substitution

Brimley parses the raw YAML file _as a string_ first to interpolate environment variables.

### Syntax

- **Required**: `${VAR_NAME}` - Raises error if missing.
    
- **Default**: `${VAR_NAME:default_value}`.
    

## 3. Context Integration

|YAML Section|Context Field|Mutability|Description|
|---|---|---|---|
|`brimley`|`ctx.settings`|Read-Only|Internal framework settings.|
|`config`|`ctx.config`|Read-Only|User-defined configuration (API keys, constants).|
|`state`|`ctx.app`|Mutable|Initial values for the shared state dictionary.|
|`databases`|`ctx.databases`|Managed|Connection definitions.|
|`mcp`|`ctx.mcp` (or runtime MCP settings)|Read-Only|Embedded MCP server behavior and transport settings.|
|`auto_reload`|`ctx.auto_reload`|Read-Only|Watch-mode interval/debounce/filter settings used by REPL and runtime controller.|
|`execution`|`ctx.execution`|Read-Only|Synchronous execution thread pool, timeout, and queue controls.|

### Updated Context Structure

```
class BrimleyContext(Entity):
    settings: FrameworkSettings     # from 'brimley'
    config: AppConfig               # from 'config'
    mcp: MCPSettings                # from 'mcp'
    auto_reload: AutoReloadSettings # from 'auto_reload'
    execution: ExecutionSettings    # from 'execution'
    app: Dict[str, Any]             # from 'state'
    databases: Dict[str, Any]       # from 'databases'
    
    # ... registries ...
```

  ## 4. CLI Override Notes

  - `brimley repl --watch|--no-watch` overrides `auto_reload.enabled`.
  - `brimley mcp-serve --watch|--no-watch` overrides `auto_reload.enabled`.
  - `brimley mcp-serve --host/--port` overrides `mcp.host` and `mcp.port`.
  - Runtime execution behavior is controlled by `execution.*` (no CLI override in 0.4).

  ### Transport Note (0.4)

  - `mcp.transport` is part of runtime settings, but current Brimley REPL/`mcp-serve` startup paths run FastMCP over SSE in 0.4.
  - In hybrid workflows, REPL remains loopback-control-plane oriented and does not share terminal `stdio` with MCP transport.

  Precedence: CLI override > config > model default.