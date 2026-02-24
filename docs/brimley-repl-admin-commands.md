# Brimley REPL Admin Commands

> Version 0.4

To improve observability and usability, the Brimley REPL supports "Admin Commands". These are meta-commands prefixed with `/` that interact with the Brimley runtime itself rather than executing business logic functions.

## 1. Syntax

All admin commands start with a forward slash `/`. This distinguishes them from function names (which must start with an alphanumeric character) and prevents namespace collisions.

**Format**: `/<command> [arguments]`

## 2. Command Reference

|   |   |   |
|---|---|---|
|**Command**|**Target Pillar**|**Description**|
|`/settings`|`ctx.settings`|Dumps the internal framework configuration (read-only).|
|`/config`|`ctx.config`|Dumps the user application configuration (read-only).|
|`/state`|`ctx.app`|Dumps the current mutable application state.|
|`/functions`|`ctx.functions`|Lists all registered functions and their types.|
|`/entities`|`ctx.entities`|Lists all registered entities.|
|`/databases`|`ctx.infrastructure`|Lists configured database connections.|
|`/reload`|Runtime reload engine|Runs one immediate reload cycle and prints standardized reload summary/diagnostics.|
|`/errors [--limit N] [--offset N] [--history]`|Runtime diagnostics set|Shows persisted runtime diagnostics with pagination and optional resolved-history view.|
|`/help`|N/A|Lists available admin commands.|
|`/quit`|N/A|Exits the REPL.|
|`/exit`|N/A|Alias for `/quit`.|

## 3. Interaction Logic

The REPL loop will be modified to intercept input before dispatching:

1. **Input Capture**: Read user input.
    
2. **Prefix Check**:
    
    - **Starts with `/`**: Route to Admin Command Handler.
        
    - **Is `quit` or `exit`**: Execute `/quit` logic (for convenience), or prompt user to use `/quit`.
        
    - **Otherwise**: Treat as a Function Call and pass to `dispatcher`.
        

## 4. Output Formatting

- **Context Objects (`/settings`, `/config`, `/state`)**:
    
    - Output as pretty-printed JSON.
        
    - Pydantic models: `model_dump_json(indent=2)`.
        
    - Dictionaries: `json.dumps(indent=2, default=str)`.
        
- **Registries (`/functions`, `/entities`)**:
    
    - Output as a formatted list or table.
        
    - Example: `[python] calculate_tax`

- **Reload and Diagnostics (`/reload`, `/errors`)**:

    - `/reload` prints reload status summary (functions/entities/tools, blocked domains, diagnostics count) and emits diagnostics when present.

    - `/errors` supports `--limit`, `--offset`, and `--history` for persisted runtime error browsing.