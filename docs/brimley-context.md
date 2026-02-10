# Brimley Context

> Version 0.2

The `BrimleyContext` is the central nervous system of a Brimley application. It is a singleton-per-request (or singleton-per-session) object that is injected into every function execution. It holds configuration, state, and access to the core registries.

## The Context Object

The Context is an implementation of the Entity pattern, but it serves as the container for all other entities and functions.

```
class BrimleyContext(Entity):
    app: Dict[str, Any]
    config: Settings
    functions: Registry[BrimleyFunction]
    entities: Registry[Entity]  # <--- NEW
    databases: Dict[str, Any]
```

|**Attribute**|**Category**|**Mutability**|**Description**|
|---|---|---|---|
|`app`|State|**Mutable**|Global or session-specific shared state.|
|`config`|Environment|**Read-Only**|Static configuration loaded at startup.|
|`functions`|Logic|**Resolved**|Registry of internal Brimley functions.|
|`entities`|Domain|**Resolved**|Registry of domain models and data schemas.|
|`databases`|Infrastructure|**Managed**|Named SQL connection pools for data persistence.|

### Fields

1. **`app`**:
    
    - **Type**: `Dict[str, Any]`
        
    - **Purpose**: Mutable, application-level state. This is where you store data that needs to persist across function calls within a session or request lifecycle.
        
    - **Access**: `ctx.app["current_user"]`
    
2. **`config`**:
    
    - **Type**: `pydantic_settings.BaseSettings`
    
    - **Purpose**: Immutable global configuration loaded from environment variables (e.g., `BRIMLEY_ENV`, `BRIMLEY_DB_URL`).
        
    - **Access**: `ctx.config.app_name`
        
3. **`functions`**:
    
    - **Type**: `Registry[BrimleyFunction]`
        
    - **Purpose**: The lookup table for all executable capabilities available to the system.
        
    - **Access**: `ctx.functions.get("calculate_tax")`
        
4. **`entities`** (New in v0.2):
    
    - **Type**: `Registry[Entity]`
        
    - **Purpose**: The central repository for all domain models and data schemas.
        
    - **Built-ins**:
        
        - `ContentBlock`
            
        - `PromptMessage`
            
    - **Access**: `ctx.entities.get("UserProfile")`
        
5. **`databases`**:
    
    - **Type**: `Dict[str, Any]`
        
    - **Purpose**: A registry of active database connection pools (Phase 2).
        

## Lifecycle

1. **Initialization**:
    
    - The `BrimleyContext` is instantiated at the entry point of the application (CLI start or Server boot).
        
    - Environment variables are loaded into `config`.
        
    - **Built-in Entities** (`ContentBlock`, `PromptMessage`) are automatically registered in `entities`.
        
2. **Hydration (Discovery)**:
    
    - The **Discovery Engine** scans the file system.
        
    - Found **Functions** are registered into `ctx.functions`.
        
    - Found **Entities** (defined in YAML) are registered into `ctx.entities`.
        
3. **Execution**:
    
    - When a request comes in (or a CLI command is run), the `context` is passed to the dispatcher.
        
    - Functions receive the `context` as their first argument (or via dependency injection), allowing them to access config, other functions, or look up entity definitions.