# Brimley 0.3 CLI & REPL Harness
> Version 0.3

The CLI is the primary interface for invoking and testing functions. It is designed to be "pipe-friendly" for automation while providing a rich interactive environment for developers.

## 1. Global Command Syntax

The CLI follows a standard structure where the root directory is an optional global argument.

```
brimley [ROOT_DIR] [COMMAND] [ARGS]
```

- **`ROOT_DIR`**: (Optional) The directory to scan for Brimley functions. Defaults to the current working directory (`.`).
    
- **`COMMAND`**: One of `invoke`, `repl`, `mcp-serve`, or `build`.
    

## 2. Commands

### `brimley [ROOT_DIR] invoke [FUNCTION_NAME] --input [PATH_OR_YAML]`

Used for single-shot execution.

- **Process:**
    
    1. **Load:** Initialize `BrimleyContext` and scan `ROOT_DIR`.
        
    2. **Input Resolution:** * If `PATH_OR_YAML` is a valid file path, parse the file (YAML or JSON).
        
        - Otherwise, parse the string as inline YAML.
            
        - If parsing fails, exit with: `Error: Invalid YAML format in [FILE/STRING].`
            
    3. **Execution:** Resolve/execute through Brimley's standard invoke pipeline (`execute_function_by_name`), which performs function lookup, argument resolution, and dispatcher execution.
        
    4. **Output:** Print _only_ the function result to `STDOUT`. All system logs or errors must go to `STDERR`.
        

### `brimley [ROOT_DIR] repl [--mcp|--no-mcp] [--watch|--no-watch]`

Used for an interactive, stateful session.

- **MCP Flags:**
    - `--mcp`: force embedded MCP startup if tool functions are present.
    - `--no-mcp`: force embedded MCP off.
    - No flag: use configuration/default (`mcp.embedded` from `brimley.yaml`).

- **Watch Flags:**
    - `--watch`: force auto-reload watcher on.
    - `--no-watch`: force auto-reload watcher off.
    - No flag: use configuration/default (`auto_reload.enabled` from `brimley.yaml`).

- **Startup:**
    
    - Print: `[SYSTEM] Scanning [ROOT_DIR]...`
        
    - Print: `[SYSTEM] Loaded [N] functions: [name1], [name2]...` (or show the "Wall of Shame" if errors occur).
        
- **Prompt:** `brimley >` 

- **Admin Commands:**
    - The REPL supports meta-commands prefixed with `/` for observability.
    - See [Admin Commands Reference](brimley-repl-admin-commands.md) for `/settings`, `/config`, `/state`, `/functions`, `/entities`, `/databases`, `/reload`, and `/help`.
    
- **Interactive Parsing Logic:**
    
    - **`exit` | `quit`**: Terminate the session.
        
    - **`reset`**: Clear `context.app` and re-scan `ROOT_DIR`.
        
    - **`[NAME] @[PATH]`**: Invoke function using a specific YAML/JSON file for arguments.
    
    - **`[NAME] [ARGS...]`**: Invoke function with smart inline parsing.
        - **Object Fallback (`{...}`):** If payload starts with `{` and ends with `}`, parse as YAML/JSON object map.
        - **Token Mode:** Otherwise parse with `shlex.split(...)`.
            - Tokens matching `key=value` are treated as keyword arguments.
            - Other tokens are treated as positional arguments, mapped to inline argument order.
            - Scalar token values are YAML-cast (`100` → int, `true` → bool, `null` → None).
        - Mixed forms are supported (e.g., `calculate_tax 100 rate=11`).
        
    - **`[NAME]` (No Arguments)**: Trigger **Multi-line Input Mode**.
        
        - Prompt changes to `...` or similar.
            
        - Read lines until an **empty line** or **EOF marker** is encountered.
            
        - Parse the accumulated lines as YAML.

### `brimley [ROOT_DIR] mcp-serve [--watch|--no-watch] [--host HOST] [--port PORT]`

Runs Brimley as a non-REPL MCP server using FastMCP over SSE.

- **Watch Flags:**
    - `--watch`: enable host-managed auto-reload watcher lifecycle.
    - `--no-watch`: disable watcher lifecycle.
    - No flag: use configuration/default (`auto_reload.enabled` from `brimley.yaml`).

- **Network Overrides:**
    - `--host`: override `mcp.host`
    - `--port`: override `mcp.port`

- **Behavior:**
    - scans and registers Brimley functions/entities
    - serves only functions exposed as MCP tools (`mcp: { type: tool }`)
    - exits successfully with warning if no MCP tools are discovered
    - exits with error if FastMCP is required but unavailable
            
### `brimley [ROOT_DIR] build [--output PATH]`

Compiles non-Python assets into a generated Python shim module for runtime/compiled discovery.

- **Process:**

    1. **Scan:** Discover SQL/template functions from `ROOT_DIR` using standard scanner behavior.

    2. **Generate:** Emit a `brimley_assets.py` module (or custom `--output`) containing decorated shim functions.

    3. **Bridge:** Allow runtime reflection discovery (`scan_module`) to discover SQL/template assets via generated Python metadata.

- **Flags:**
    - `--output`, `-o`: optional output path for generated module file.

- **Output:**
    - Success message with generated file path and counts (`sql`, `templates`).
    - Warning when scanner diagnostics were present during build.


## 3. Argument Merging Logic

Before a handler is called, the engine merges data from three sources:

1. **Defaults:** Defined in the function's `arguments.inline` specification.
    
2. **Context:** Values injected via `from_context` (e.g., pulling `user_id` from `context.app`).
    
3. **Input:** The data provided via `--input`, the REPL line, or the REPL `@file`.
    

**Priority:** Input > Context > Defaults.

For REPL token mode specifically:
- Positional values map first in inline argument order.
- Keyword values are applied next.
- Duplicate assignment (same argument from positional + keyword, or repeated keyword) is rejected.
- Unknown keyword names are rejected.

## 4. Output & Error Diagnostics

### Output Standards

- **Function Results:** Printed as raw strings (for templates) or formatted JSON (for objects/lists).
    
- **REPL Status:** Prefixed with `[SYSTEM]` to distinguish engine activity from function output.
    
- **Success Indicators:** In REPL, use `[SYSTEM] Executing [NAME]...` before showing results.
    

### Standard Error Messages

- **Missing File:** `Error: Input file '[FILENAME]' not found.`
- **Invalid Object Input:** `Invalid argument syntax: ...`
- **Invalid Tokenization:** `Invalid argument token: '=...'. Expected key=value or positional value.`
- **Too Many Positional Values:** `Too many positional arguments provided.`
- **Unknown Keyword:** `Unknown argument: '[ARG_NAME]'.`
- **Duplicate Assignment:** `Duplicate argument assignment for '[ARG_NAME]'.`
    
- **Missing Function:** `Error: Function '[NAME]' not found in registry.`
    
- **Validation Failure:** `Error: Argument '[ARG_NAME]' expected [TYPE], got [VALUE].`
    

## 5. REPL State Management

In `repl` mode, the `BrimleyContext` is persistent.

- Modifications to `context.app` made by one function call are available to subsequent calls.
    
- This allows for testing multi-step workflows (e.g., a "setup" function followed by a "logic" function).

Nested function composition inside handlers follows the same pipeline via `BrimleyContext.execute_function_by_name(...)`.
    

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

# Positional input
brimley > calculate_tax 100 11

# Keyword input
brimley > calculate_tax amount=100 rate=11

# Mixed positional + keyword
brimley > calculate_tax 100 rate=11

# Quote tokens containing spaces
brimley > create_user name="Bob Smith" role=admin

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

### C. Build Assets

```
brimley ./tools build
# [SYSTEM] Generated assets at ./tools/brimley_assets.py (sql=2, templates=1)
```

```
brimley ./tools build --output ./dist/brimley_assets.py
```

## Embedded FastMCP Server

If your Brimley project contains any functions tagged with `mcp: type: tool`, starting the REPL can spin up an embedded FastMCP server when MCP embedding is enabled via configuration or CLI flags.

Because the interactive REPL requires control of your terminal input and output, the embedded FastMCP server runs on a background asynchronous task using the **SSE (Server-Sent Events) transport** via HTTP.

**Console Output Example:**

```
Loading Brimley Configuration from brimley.yaml...
Discovered 12 functions (3 exposed as MCP tools).
[MCP] Background FastMCP server running at [http://127.0.0.1:8000/sse](http://127.0.0.1:8000/sse)

brimley>
```

You can continue to execute functions manually in the `brimley>` prompt while an external LLM connects to port 8000 to execute functions concurrently.

If MCP tools are discoverable but FastMCP is not installed, REPL stays interactive and logs a warning instead of failing startup.

_(Note: MCP server settings like host, port, transport, and embedded mode can be set in the `mcp:` section of `brimley.yaml`, and embedded mode can be overridden by CLI flags.)_

## Auto-Reload Watch Mode

When watch mode is enabled, the REPL starts a background polling watcher and triggers the same reload contract used by `/reload` when tracked files change.

- Uses include/exclude pattern filters from `auto_reload` config.
- Uses debounce to collapse burst updates into one reload cycle.
- Applies partitioned reload policy (entities → functions → MCP tools).
- Preserves currently active runtime domains when reload fails in downstream domains.

`/reload` remains available even when watch mode is disabled.