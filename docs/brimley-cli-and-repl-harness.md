# Brimley 0.2 CLI & REPL Harness
> Version 0.2

The CLI is the primary interface for invoking and testing functions. It is designed to be "pipe-friendly" for automation while providing a rich interactive environment for developers.

## 1. Global Command Syntax

The CLI follows a standard structure where the root directory is an optional global argument.

```
brimley [ROOT_DIR] [COMMAND] [ARGS]
```

- **`ROOT_DIR`**: (Optional) The directory to scan for Brimley functions. Defaults to the current working directory (`.`).
    
- **`COMMAND`**: Either `invoke` or `repl`.
    

## 2. Commands

### `brimley [ROOT_DIR] invoke [FUNCTION_NAME] --input [PATH_OR_YAML]`

Used for single-shot execution.

- **Process:**
    
    1. **Load:** Initialize `BrimleyContext` and scan `ROOT_DIR`.
        
    2. **Input Resolution:** * If `PATH_OR_YAML` is a valid file path, parse the file (YAML or JSON).
        
        - Otherwise, parse the string as inline YAML.
            
        - If parsing fails, exit with: `Error: Invalid YAML format in [FILE/STRING].`
            
    3. **Execution:** Call `registry.get(name).run(context, resolved_args)`.
        
    4. **Output:** Print _only_ the function result to `STDOUT`. All system logs or errors must go to `STDERR`.
        

### `brimley [ROOT_DIR] repl`

Used for an interactive, stateful session.

- **Startup:**
    
    - Print: `[SYSTEM] Scanning [ROOT_DIR]...`
        
    - Print: `[SYSTEM] Loaded [N] functions: [name1], [name2]...` (or show the "Wall of Shame" if errors occur).
        
- **Prompt:** `brimley >` 
    
- **Interactive Parsing Logic:**
    
    - **`exit` | `quit`**: Terminate the session.
        
    - **`reset`**: Clear `context.app` and re-scan `ROOT_DIR`.
        
    - **`[NAME] @[PATH]`**: Invoke function using a specific YAML/JSON file for arguments.
        
    - **`[NAME] [YAML_STRING]`**: Invoke function with single-line inline YAML.
        
    - **`[NAME]` (No Arguments)**: Trigger **Multi-line Input Mode**.
        
        - Prompt changes to `...` or similar.
            
        - Read lines until an **empty line** or **EOF marker** is encountered.
            
        - Parse the accumulated lines as YAML.
            

## 3. Argument Merging Logic

Before a handler is called, the engine merges data from three sources:

1. **Defaults:** Defined in the function's `arguments.inline` specification.
    
2. **Context:** Values injected via `from_context` (e.g., pulling `user_id` from `context.app`).
    
3. **Input:** The data provided via `--input`, the REPL line, or the REPL `@file`.
    

**Priority:** Input > Context > Defaults.

## 4. Output & Error Diagnostics

### Output Standards

- **Function Results:** Printed as raw strings (for templates) or formatted JSON (for objects/lists).
    
- **REPL Status:** Prefixed with `[SYSTEM]` to distinguish engine activity from function output.
    
- **Success Indicators:** In REPL, use `[SYSTEM] Executing [NAME]...` before showing results.
    

### Standard Error Messages

- **Missing File:** `Error: Input file '[FILENAME]' not found.`
    
- **Invalid Input:** `Error: Invalid YAML format in [FILE/STRING].`
    
- **Missing Function:** `Error: Function '[NAME]' not found in registry.`
    
- **Validation Failure:** `Error: Argument '[ARG_NAME]' expected [TYPE], got [VALUE].`
    

## 5. REPL State Management

In `repl` mode, the `BrimleyContext` is persistent.

- Modifications to `context.app` made by one function call are available to subsequent calls.
    
- This allows for testing multi-step workflows (e.g., a "setup" function followed by a "logic" function).
    

## 6. Usage Examples

### A. Single-Shot (Invoke)

**Using an Inline String:**

```
brimley ./my_functions invoke get_user --input "{uid: 101}"
```

**Using a YAML File (for complex inputs):**

```
brimley ./my_functions invoke process_batch --input ./tests/inputs/batch_data.yaml
```

**Piping Result to a File:**

```
# System logs go to stderr, only the result goes to the file
brimley invoke list_orders --input "{status: pending}" > pending_orders.json
```

### B. Interactive Session (REPL)

```
$ brimley ./tools repl
[SYSTEM] Scanning ./tools...
[SYSTEM] Loaded 3 functions: get_user, update_score, render_report

brimley > get_user {uid: 42}
[SYSTEM] Executing get_user...
{ "id": 42, "name": "Arthur Dent", "role": "User" }

# Using the @ prefix for a file-based input
brimley > update_score @./test_data/score_update.yaml
[SYSTEM] Executing update_score...
{ "status": "updated", "new_score": 1500 }

# Using Multi-line Mode for a complex template test
brimley > render_report
... user_id: 42
... title: "End of Year Review"
... include_metrics: true
... [Empty Line Entered]
[SYSTEM] Executing render_report...
# Report for Arthur Dent
Your current score is 1500.

brimley > quit
[SYSTEM] Goodbye.
```