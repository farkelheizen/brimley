# Brimley Discovery & Loader Specification

> Version 0.2

The Discovery Engine is the heart of Brimley. It translates files on disk into executable `BrimleyFunction` objects and schema-defined `Entity` objects, populating the `BrimleyContext`.

## 1. The Scanning Algorithm

1. **Initialization:** The engine accepts a `root_dir`.
    
2. **Traversal:** Use `os.walk` or `pathlib.Path.rglob("*")` to visit every file.
    
3. **Identification (The 500-Character Rule):** For `.py`, `.sql`, `.md`, and `.yaml` files, the scanner reads the first 500 characters to determine the file type.
    
    It looks for a `type:` marker.
    
    - **Match:** `type: [something]_function` -> Identified as **Function**.
        
    - **Match:** `type: entity` -> Identified as **Entity**.
        
    - **No Match:** Ignore the file (Silent Ignore).
        
4. **Parsing:** The scanner delegates to a specific parser based on the identified type:
    
    - **Functions:**
        
        - `sql_function` -> `parse_sql_file`
            
        - `template_function` -> `parse_template_file`
            
        - `python_function` -> `parse_python_file`
            
    - **Entities:**
        
        - `entity` -> `parse_entity_file` (Parses YAML definition into an `Entity` schema/model).
            

## 2. Validation Flow

For every identified file:

### For Functions

1. **Schema Check:** Does the metadata contain `name` and `return_shape`?
    
2. **Name Check:** Does `name` match `^[a-zA-Z][a-zA-Z0-9_-]{1,63}$`?
    
3. **Registry Check:** Is `name` unique within `ctx.functions`?
    
4. **Handler Check:** (Python only) Can the `handler` be resolved?

5. **MCP Metadata Check:** If an `mcp` block exists, validate its schema (e.g., currently `type: tool` with optional description override). Invalid MCP metadata should produce diagnostics and not crash scanning.
    

### For Entities

1. **Schema Check:** Does the YAML contain `name` and a valid schema definition (e.g., `fields` or Pydantic-compatible structure)?
    
2. **Name Check:** Does `name` match the entity naming convention (PascalCase recommended)?
    
3. **Registry Check:** Is `name` unique within `ctx.entities`?
    

## 3. Error Accumulation

The Loader must **not** raise an exception on the first error. It must finish the scan of the entire directory, collecting all `BrimleyDiagnostic` objects.

If critical errors (parsing failures, invalid names, duplicates) occur, the application should display the "Wall of Shame" (a formatted list of diagnostics) and refuse to start.

## 4. Successful Registration

A successful scan produces a `BrimleyScanResult` containing two lists:

1. **`functions`**: A list of `BrimleyFunction` objects.
    
2. **`entities`**: A list of `Entity` definitions.
    

These are then bulk-registered into the `BrimleyContext`:

- `ctx.functions.register_all(scan_result.functions)`
    
- `ctx.entities.register_all(scan_result.entities)`