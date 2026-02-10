# Brimley Context

> Version 0.2

The `BrimleyContext` is the central nervous system of a Brimley application.

## The Context Object

```
class BrimleyContext(Entity):
    settings: FrameworkSettings     # Internal Framework Config
    config: AppConfig               # User Application Config
    app: Dict[str, Any]             # Mutable Application State
    
    functions: Registry[BrimleyFunction]
    entities: Registry[Entity]
    databases: Dict[str, Any]
```

|**Attribute**|**Source (YAML)**|**Mutability**|**Description**|
|---|---|---|---|
|`settings`|`brimley:`|**Read-Only**|Framework settings (env, logging, app name).|
|`config`|`config:`|**Read-Only**|User-defined configuration (API keys, constants).|
|`app`|`state:`|**Mutable**|Global shared state. Seeded from YAML, modified at runtime.|
|`functions`|N/A|**Resolved**|Registry of internal Brimley functions.|
|`entities`|N/A|**Resolved**|Registry of domain models.|
|`databases`|`databases:`|**Managed**|Connection pools.|

## Fields

1. **`settings`**:
    
    - **Type**: `FrameworkSettings`
        
    - **Purpose**: Internal framework configuration loaded from the `brimley` section of `brimley.yaml` (e.g., environment, log level).
        
    - **Access**: `ctx.settings.env`
        
2. **`config`**:
    
    - **Type**: `AppConfig`
        
    - **Purpose**: User-defined application configuration loaded from the `config` section of `brimley.yaml`.
        
    - **Access**: `ctx.config.support_email`
        
3. **`app`**:
    
    - **Type**: `Dict[str, Any]`
        
    - **Purpose**: Mutable, application-level state. Seeded from the `state` section of `brimley.yaml`.
        
    - **Access**: `ctx.app["maintenance_mode"]`
        
4. **`functions`**:
    
    - **Type**: `Registry[BrimleyFunction]`
        
    - **Purpose**: The lookup table for all executable capabilities available to the system.
        
    - **Access**: `ctx.functions.get("calculate_tax")`
        
5. **`entities`**:
    
    - **Type**: `Registry[Entity]`
        
    - **Purpose**: The central repository for all domain models and data schemas.
        
    - **Built-ins**:
        
        - `ContentBlock`
            
        - `PromptMessage`
            
    - **Access**: `ctx.entities.get("UserProfile")`
        
6. **`databases`**:
    
    - **Type**: `Dict[str, Any]`
        
    - **Purpose**: A registry of active database connection pools (Phase 2).
        

## Lifecycle

1. **Initialization**:
    
    - The `BrimleyContext` is instantiated at the entry point of the application (CLI start or Server boot).
        
    - `brimley.yaml` is loaded and interpolated.
        
    - `settings`, `config`, and `app` (initial state) are populated.
        
    - **Built-in Entities** (`ContentBlock`, `PromptMessage`) are automatically registered in `entities`.
        
2. **Hydration (Discovery)**:
    
    - The **Discovery Engine** scans the file system.
        
    - Found **Functions** are registered into `ctx.functions`.
        
    - Found **Entities** (defined in YAML) are registered into `ctx.entities`.
        
3. **Execution**:
    
    - When a request comes in (or a CLI command is run), the `context` is passed to the dispatcher.
        
    - Functions receive the `context` as their first argument (or via dependency injection), allowing them to access settings, config, state, or look up entity definitions.