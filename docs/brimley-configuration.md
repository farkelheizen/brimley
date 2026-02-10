# Brimley Configuration

> Version 0.2

Brimley applications are configured via a single YAML file (`brimley.yaml`) located in the project root.

## 1. The Configuration File: `brimley.yaml`

The configuration file is divided into four sections, mapping directly to the Context:

1. **`brimley`**: Framework-level settings (maps to `ctx.settings`).
    
2. **`config`**: User-defined application configuration (maps to `ctx.config`).
    
3. **`state`**: Initial seed data for application state (maps to `ctx.app`).
    
4. **`databases`**: Definitions for SQL connections (hydrates `ctx.infrastructure`).
    

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
|state`|`ctx.app`|Mutable|Initial values for the shared state dictionary.|
|`databases`|`ctx.infrastructure`|Managed|Connection definitions.|

### Updated Context Structure

```
class BrimleyContext(Entity):
    settings: FrameworkSettings     # from 'brimley'
    config: AppConfig               # from 'config'
    app: Dict[str, Any]             # from 'state'
    
    # ... registries ...
```