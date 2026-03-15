# Brimley 0.9: CLI Functions (.yaml)

## Overview

CLI Functions wrap shell commands as first-class Brimley functions. This enables "tool-use" for legacy scripts, system utilities, or other CLI tools within the Brimley ecosystem, providing a structured interface over raw shell execution.

## 1. Specification

CLI functions are defined in standard `.yaml` files where the `type` is set to `cli_function`.

### Schema Example: `system_metrics.yaml`

```
name: get_system_load
type: cli_function
description: "Returns the current system load average using the 'uptime' command"

# MCP Configuration Block
mcp:
  type: tool

# Root-level return_shape for consistency with other function types
return_shape: SystemLoad

command: "uptime"
args: []

env:
  PATH: "/usr/bin:/bin"
  DEBUG_MODE: "{{ debug_enabled }}"

parsing:
  strategy: regex
  pattern: "load average: (?P<load_1min>\\d+\\.\\d+)"
  capture_group: "load_1min" 
```

## 2. MCP Integration

Like other Brimley functions, CLI functions can be surfaced to the Model Context Protocol using the `mcp` configuration block:

- **`mcp.type: tool`**: Exposes the CLI command as a tool. This is highly effective for giving LLMs access to local system utilities or custom automation scripts.
    
- **`mcp.type: resource`**: Good for CLI tools that strictly output state or logs.
    

## 3. Return Shapes & Output Mapping

The `return_shape` attribute defines the structural contract for the function output.

- **Unified Consistency:** CLI functions share the same metadata signature as SQL, Python, and API functions.
    
- **Parsing to Shape:** The `parsing` block (Regex or JSON strategies) transforms raw `stdout` into the Entity data defined in the `return_shape`.
    

## 4. Key Features

- **Input Injection:** Arguments are injected into `command`, `args`, or `env` via Jinja2.
    
- **Output Capture:** Captures `stdout` for results and `stderr` for diagnostics.
    
- **Error Handling:** Non-zero exit codes trigger `BrimleyExecutionError`.
    

## 5. Security & Constraints

- **Sandboxing:** Restricted `cwd` and environment variable whitelisting.
    
- **Timeout:** Mandatory `timeout_seconds` to prevent hanging processes.
    

## 6. Testing & Mocking

- **Dry Run:** Logs the command without execution.
    
- **Mocking:** The `MockRegistry` can intercept CLI calls to simulate `stdout` or full result objects, ensuring portability across environments.
    

## 7. Execution Flow

1. **Discovery:** Scanner detects `.yaml` files with `type: cli_function`.
    
2. **MCP Registration:** Function is registered with the MCP adapter if the `mcp` block is specified.
    
3. **Dispatch:** Routed to `CliRunner`.
    
4. **Execution:** Process spawned via `asyncio.create_subprocess_exec`.
    
5. **Processing:** `stdout` is captured and parsed.
    
6. **Return:** Parsed object is validated against `return_shape` and returned.
## Unresolved Architectural Feedback

*   **Security of CLI Runners:** Wrapping Shell commands in `.yaml` is very powerful but opens vectors for remote code execution if arguments aren’t strictly sanitized. What boundaries will the Runner expose to prevent prompt injection from tricking an LLM into running destructive shell commands?
