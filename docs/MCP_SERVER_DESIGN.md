# Design Document: Brimley MCP Server

## 1. Overview
The **Brimley MCP Server** is a standalone, executable wrapper around the Brimley Engine. It allows any application to host a "Data & Tools" agent capability by simply providing a directory of configuration files and a database.

It utilizes the **Model Context Protocol (MCP)** to expose these tools standardly to generic AI clients (Claude Desktop, Cursor, Custom Apps).

## 2. Architecture

The system consists of three layers:

1.  **Host Application (The Environment)**
    *   Manages the file system (the `tools/` directory, the SQLite `.db` file).
    *   Launches the Brimley MCP Server as a subprocess (Stdio).
2.  **Brimley MCP Server (The Bridge)**
    *   CLI Entrypoint.
    *   Loads `BrimleyEngine`.
    *   **Adapter Layer:** Dynamically converts Brimley's internal tool schema into FastMCP tool registrations (Pydantic models).
3.  **Brimley Core (The Engine)**
    *   Executes the actual SQL and validations.

## 3. CLI Interface

The server will be a command-line application installed via pip.

**Command Name:** `brimley-mcp`

**Arguments:**

| Argument | Flag | Env Var | Description |
| :--- | :--- | :--- | :--- |
| **Database Path** | `--db-path`, `-d` | `BRIMLEY_DB_PATH` | Path to the SQLite database file. |
| **Tools Directory** | `--tools-dir`, `-t` | `BRIMLEY_TOOLS_DIR` | Path to the directory containing JSON/YAML tool definitions. |
| **Extensions File** | `--extensions-file`, `-e` | `BRIMLEY_EXTENSIONS_FILE` | Path to a Python file containing custom `@brimley.register` logic. |
| **Server Name** | `--name`, `-n` | `BRIMLEY_SERVER_NAME` | Name exposed to the MCP client (default: "Brimley Server"). |

**Configuration Precedence:**
1.  **CLI Argument** (Highest priority)
2.  **Environment Variable** (`.env` supported)
3.  **Defaults** (e.g., specific files in current working directory)

**Example Usage:**

```bash
# Explicit
brimley-mcp start --db-path ./user_data.db --tools-dir ./my_tools

# Using Env Vars
export BRIMLEY_DB_PATH=./data.db
brimley-mcp start
```

## 4. The Adapter Layer (Technical Detail)

The core challenge is translating Brimley's *dynamic* schemas (runtime dictionaries) into FastMCP's *static* expectations (Type Hints / Pydantic Models).

**The Flow:**
1.  **Reflection:** The server iterates over `engine.tools.values()`.
2.  **Model Synthesis:** For each tool:
    *   Extract `arguments` schema.
    *   Map Brimley types (`int`, `string`, `bool`) to Python types.
    *   Construct a `pydantic.BaseModel` dynamically using `create_model`.
3.  **Function Generation:**
    *   Generate a wrapper function that accepts the specific arguments defined in the tool.
    *   *Critical:* FastMCP uses `inspect.signature` to advertise tools to the LLM. The wrapper must intentionally "fake" its signature to match the dynamic arguments.
4.  **Execution:**
    *   The wrapper calls `engine.execute_tool(name, args)`.
    *   Returns the result as JSON string or structured data.

## 5. Logging & Observability

Because MCP uses `stdout` for JSON-RPC communication, strict IO discipline is required.

1.  **Stdio Isolation:** The application must NEVER print to `stdout`. All logs, debug information, and internal Brimley warnings must be routed to `stderr`.
2.  **Debug Flags:** The CLI will support a `--debug` flag that configures the Python logging handler to output detailed DEBUG logs to `stderr`, allowing developers to trace SQL queries and tool execution without breaking the protocol.

## 6. Integration Patterns

### A. Local Usage

**Claude Desktop / Cursor:**
Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "my-data": {
      "command": "brimley-mcp",
      "args": [
        "start", 
        "--db-path", "/absolute/path/to/data.db", 
        "--tools-dir", "/absolute/path/to/tools"
      ]
    }
  }
}
```

**VS Code (Project Settings):**
Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "my-data": {
      "command": "brimley-mcp",
      "args": [
        "start",
        "--db-path", "${workspaceFolder}/data/local.db", 
        "--tools-dir", "${workspaceFolder}/tools"
      ]
    }
  }
}
```

### B. App Embedding
A host Node.js or Python app can spin up the server to provide tools to an AI running in a different context.

## 7. Project Structure Changes

We will move the logic currently in `examples/mcp_server/server.py` into the core library structure, potentially as a separate package namespace or an "extras" module.

Proposed Location: `src/brimley/mcp/`
