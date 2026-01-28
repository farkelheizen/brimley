# Brimley MCP Server Example

This directory contains a complete example of a Model Context Protocol (MCP) server powered by Brimley. It demonstrates how to expose Brimley tools and custom SQL functions (UDFs) to AI assistants (like Claude or IDEs) via the MCP standard.

## What is this?

- **`server.py`**: A minimal MCP server using `fastmcp` that wraps a `BrimleyEngine`.
- **`extensions.py`**: A Python file defining custom SQLite functions (User Defined Functions) using the `@register_sqlite_function` decorator.
- **`tools/`**: A directory containing YAML configuration files for Brimley tools.
- **`setup_db.py`**: A helper script to generate a sample SQLite database.

## How to Run

### 1. Prerequisites

Ensure you have Python 3.10+ installed.

### 2. Setup Dependencies

You can run this example using `poetry` (recommended if you are developing Brimley) or `pip`.

#### Option A: Using Poetry (Recommended)

From the root of the repository:

```bash
# Install root project dependencies
poetry install

# Switch to the example directory 
cd examples/mcp_server

# Install example dependencies (fastmcp is required)
poetry add fastmcp
# OR if you just want to run in the current venv:
pip install fastmcp
```

#### Option B: Using Pip

Create a virtual environment in `examples/mcp_server`:

```bash
cd examples/mcp_server
python3 -m venv .venv
source .venv/bin/activate

# Install fastmcp
pip install fastmcp

# Install brimley from the parent directory in editable mode
pip install -e ../../
```

### 3. Initialize the Database

This creates a `demo.db` file with sample user data.

```bash
python3 setup_db.py
```

### 4. Run the Server

You can run the server directly with Python or using the `fastmcp` CLI.

**Using Python:**
```bash
python3 server.py
```
*Note: This will start the server. By default, FastMCP over stdio doesn't print output to the console unless configured to debug.*

**Using FastMCP CLI (for testing/inspection):**
```bash
# If using poetry
poetry run fastmcp run server.py

# If using pip/venv
fastmcp run server.py
```

### 5. Using with VS Code

To use this server with GitHub Copilot or other MCP clients in VS Code, you need to configure it in your generic MCP client settings (e.g., `~/Library/Application Support/Code/User/globalStorage/mcp-servers.json` or project specific `.vscode/mcp.json` if supported by your extension).

Here is the configuration you would add:

```json
{
  "servers": {
    "brimley": {
      "command": "/ABSOLUTE/PATH/TO/.venv/bin/python",
      "args": [
        "/ABSOLUTE/PATH/TO/brimley/examples/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "/ABSOLUTE/PATH/TO/brimley/src"
      }
    }
  }
}
```

*Important:* You must point `command` to the **Python executable inside your virtual environment** (where `fastmcp` is installed), not the system `python3`. 
If you set up the project with `poetry install` at the root, this path is usually in `.venv/bin/python` inside the project root, or found via `poetry env info --path`. 
If you created a specific venv for this example, point to that one (e.g. `examples/mcp_server/.venv/bin/python`).

*Note: You must use absolute paths because the MCP client launches the process independently.*


## Testing with the Inspector


The `fastmcp` library comes with an inspector to test your tools.

```bash
fastmcp dev server.py
# or
poetry run fastmcp dev server.py
```

This will launch a web interface where you can try the `get_vip_users` tool.

## Key Files Explained

- **`extensions.py`**: Defines `vip_score`.
  ```python
  @register_sqlite_function("vip_score", 1)
  def vip_score(purchase_count): ...
  ```
- **`tools/get_vip_users.yaml`**: Uses that function.
  ```yaml
  sql: "SELECT ... FROM users WHERE vip_score(purchase_count) > :min_score"
  ```
- **`server.py`**: The glue.
  1. Loads `BrimleyEngine` with `extensions_file="extensions.py"`.
  2. Autos-registers the function `vip_score` into the SQLite connection.
  3. Wraps Brimley tools as MCP tools.

## License

MIT

## Author

**William W. Spratley**

* GitHub: [@farkelheizen](https://github.com/farkelheizen)