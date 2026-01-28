# Brimley MCP Server Guide

Brimley includes a built-in server that implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). This allows you to expose your local SQL tools to AI agents like Claude Desktop, Cursor, and others.

## Installation

Install Brimley with the server "extra":

```bash
pip install brimley[server]
```

Or install the dependencies manually:
```bash
pip install brimley fastmcp typer python-dotenv
```

## Usage

The server is available as a command-line interface (CLI) named `brimley-mcp`.

### Core Command

```bash
brimley-mcp start --db-path ./my.db --tools-dir ./tools
```

### Arguments

| Argument | Description | Env Var |
| :--- | :--- | :--- |
| `--db-path` | Path to your SQLite database file. | `BRIMLEY_DB_PATH` |
| `--tools-dir` | Path to the folder containing tool definitions (JSON/YAML). | `BRIMLEY_TOOLS_DIR` |
| `--extensions-file` | (Optional) Path to a Python file with custom extensions. | `BRIMLEY_EXTENSIONS_FILE` |
| `--name` | (Optional) Server name shown to the AI client. | `BRIMLEY_SERVER_NAME` |
| `--debug` | Enable debug logging to stderr. | - |

## Integration

### Claude Desktop

To use your tools in Claude (`claude-desktop`), add the server to your configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "my-data": {
      "command": "brimley-mcp",
      "args": [
        "start",
        "--db-path", "/absolute/path/to/my_data.db",
        "--tools-dir", "/absolute/path/to/tools"
      ]
    }
  }
}
```

*Note: Always use absolute paths.*

### VS Code (Cursor / Cline)

Add a `.vscode/mcp.json` file to your project:

```json
{
  "servers": {
    "project-db": {
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

## Debugging

The MCP protocol uses `stdout` (standard output) for communication. If your application prints anything to stdout (like a stray `print("hello")`), the connection will break.

Brimley handles this by strictly routing all logs to `stderr`. To see what's happening under the hood:

```bash
brimley-mcp start --db-path ... --tools-dir ... --debug
```

In Claude Desktop, you can view these logs (`stderr`) using the "Developer" tools or log viewer provided by the app.
