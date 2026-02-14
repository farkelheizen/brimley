# Brimley Configuration

> Version 0.2

Brimley applications are configured via a single YAML file (`brimley.yaml`) located in the project root.

## 1. The Configuration File: `brimley.yaml`

The configuration file is divided into six sections, mapping directly to the Context:

1. **`brimley`**: Framework-level settings (maps to `ctx.settings`).
    
2. **`config`**: User-defined application configuration (maps to `ctx.config`).
    
3. **`state`**: Initial seed data for application state (maps to `ctx.app`).
    
4. **`databases`**: Definitions for SQL connections (hydrates `ctx.databases`).

5. **`mcp`**: MCP runtime settings (mapped to MCP runtime configuration in the application context/runtime).

6. **`auto_reload`**: Watch-mode settings for polling interval, debounce, and file filters.
    

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

### Updated Context Structure

```
class BrimleyContext(Entity):
    settings: FrameworkSettings     # from 'brimley'
    config: AppConfig               # from 'config'
    mcp: MCPSettings                # from 'mcp'
    auto_reload: AutoReloadSettings # from 'auto_reload'
    app: Dict[str, Any]             # from 'state'
    databases: Dict[str, Any]       # from 'databases'
    
    # ... registries ...
```

  ## 4. CLI Override Notes

  - `brimley repl --watch|--no-watch` overrides `auto_reload.enabled`.
  - `brimley mcp-serve --watch|--no-watch` overrides `auto_reload.enabled`.
  - `brimley mcp-serve --host/--port` overrides `mcp.host` and `mcp.port`.

  Precedence: CLI override > config > model default.