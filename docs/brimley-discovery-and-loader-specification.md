# Brimley Discovery & Loader Specification
> Version 0.2

The Discovery Engine is the heart of Brimley. It translates files on disk into `BrimleyFunction` objects in the `BrimleyContext.functions` registry.

## 1. The Scanning Algorithm

1. **Initialization:** The engine accepts a `root_dir`.
    
2. **Traversal:** Use `os.walk` or `pathlib.Path.rglob("*")`.
    
3. **Identification (The 500-Character Rule):**
    
    - For `.py`, `.sql`, `.md`, and `.yaml` files, peek at the first 500 characters.
        
    - Look for the marker `type: [type]_function`.
        
    - If not found, ignore the file (Silent Ignore).
        
4. **Parsing:**
    
    - **SQL/MD/YAML:** Extract the YAML frontmatter and the "Body" (the SQL query or the Template text).
        
    - **Python:** If it contains a `type: python_function` YAML block, use the `handler` path. If it uses the `@brimley_function` decorator, use inspection/reflection.
        

## 2. Validation Flow

For every identified file:

1. **Schema Check:** Does the YAML frontmatter contain `name` and `return_shape`?
    
2. **Name Check:** Does `name` match the regex `^[a-zA-Z][a-zA-Z0-9_-]{1,63}$`?
    
3. **Registry Check:** Does this `name` already exist in the `functions` dictionary?
    
4. **Handler Check:** If it's a `python_function`, can the `handler` string be resolved to a callable?
    

## 3. Error Accumulation

The Loader must **not** raise an exception on the first error. It must finish the scan of the entire directory, collecting all `BrimleyDiagnostic` objects, and then present the "Wall of Shame" if any critical errors occurred.

## 4. Successful Registration

A successful load results in a `BrimleyFunction` object that contains:

- The validated metadata.
    
- A `run()` method that takes `(context, args)` and handles the specific execution logic for that type.