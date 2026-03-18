# Brimley Configuration

Brimley applications are configured via a single YAML file (`brimley.yaml`) located in the project root.

## 1. The Configuration File: `brimley.yaml`

The configuration file is divided into seven sections, mapping directly to the Context:

1. **`brimley`**: Framework-level settings (maps to `ctx.settings`), including the `brimley.logging` sub-section (new in 0.6).
    
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

  # Observability / Logging (Brimley 0.6+)
  logging:
    level: INFO                  # Global default level for the stderr sink
    modules:                     # Module-level overrides (Log4J-style prefix matching)
      brimley.execution: DEBUG
      fastmcp: WARNING
      sqlalchemy: WARNING
    file:
      path: logs/brimley.log     # Relative to project root, or absolute
      level: DEBUG               # File sink can be more verbose than stderr
      format: jsonl              # 'text' (default) or 'jsonl' for structured logs
      rotation: 10 MB            # 'N MB', 'daily', etc.
      retention: 7 days          # '7 days', '4 weeks', etc.
    managed: true                # Set false to disable Brimley's Loguru setup entirely

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

    # Read-only observability properties (Brimley 0.6+)
    correlation_id: str             # Current request correlation ID (ContextVar)
    external_trace_id: str          # Upstream trace ID (FastMCP request_id, else correlation_id)

    # ... registries ...
```

  ## 4. CLI Override Notes

  - `brimley repl --watch|--no-watch` overrides `auto_reload.enabled`.
  - `brimley mcp-serve --watch|--no-watch` overrides `auto_reload.enabled`.
  - `brimley mcp-serve --host/--port` overrides `mcp.host` and `mcp.port`.
  - `brimley invoke|repl|mcp-serve --log-level LEVEL` overrides the global stderr log level for this session (Brimley 0.6+).
  - `brimley invoke|repl|mcp-serve --log-module MODULE:LEVEL` overrides a module-specific log level (may be repeated, Brimley 0.6+).
  - Runtime execution behavior is controlled by `execution.*`.

  ### Logging Precedence Order (Brimley 0.6+)

  Effective log level for a given record is resolved highest-to-lowest:

  1. **Per-correlation-ID override** (REPL `/log-level-for-id` or API call)
  2. **CLI/runtime override** (`--log-level`, `--log-module`, or REPL `/log-level`)
  3. **`brimley.logging.modules`** (per-module prefix threshold in config)
  4. **`brimley.logging.level`** (global default, default: `INFO`)
  5. **Model default** (`INFO` for stderr, `DEBUG` for file sink)

  Logs are **always routed to stderr** (never stdout) to preserve the MCP JSON-RPC stream.

  ### Transport Note (0.6)

  - `mcp.transport` is part of runtime settings, but current Brimley REPL/`mcp-serve` startup paths run FastMCP over SSE in 0.6.
  - In hybrid workflows, REPL remains loopback-control-plane oriented and does not share terminal `stdio` with MCP transport.

  Precedence: CLI override > config > model default.