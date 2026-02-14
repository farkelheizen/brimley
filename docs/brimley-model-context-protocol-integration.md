# Model Context Protocol (MCP) Integration

Brimley acts as a powerful single source of truth for your organizational functions. With built-in support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/ "null"), you can seamlessly expose your Brimley functions as tools to Large Language Models (LLMs) and agents like Claude, LangGraph, or AutoGen.

Under the hood, Brimley uses [FastMCP](https://github.com/jlowin/fastmcp) to create and host these tools.

FastMCP is optional at install time. Brimley only requires it when you actually register or run MCP tools.

## Exposing a Function as an MCP Tool

To expose a Brimley function as an MCP tool, simply add the `mcp` block to the function's YAML frontmatter and set its `type` to `tool`.

```
---
name: create_user
type: sql_function
description: "Creates a new user in the database"
arguments:
  inline:
    username:
      type: string
      description: "The desired username"
    role:
      type: string
      default: "viewer"
  support_email:
    type: string
    from_context: "config.support_email"
mcp:
  type: tool
---
INSERT INTO users (username, role, created_by) 
VALUES ({{ args.username }}, {{ args.role }}, '{{ args.support_email }}')
```

### Argument Filtering (Smart Context)

When Brimley exposes a function via MCP, it **intelligently filters the tool signature**. LLMs do not know about your internal configuration, secrets, or context variables.

In the example above:

- The LLM will **only** be prompted to provide the `username` and `role` arguments.
    
- The `support_email` argument (sourced from `from_context`) is hidden from the LLM's schema entirely.
    
- When the LLM calls the tool, Brimley intercepts the call, fetches `config.support_email` from the active `BrimleyContext`, injects it, and executes the function seamlessly.
    

## The Embedded REPL Server

When you start the Brimley REPL via the CLI (`brimley repl`), Brimley discovers all functions tagged with `mcp: type: tool`. If any are found and MCP embedding is enabled (`mcp.embedded: true`, or via CLI override), Brimley spins up an embedded FastMCP server in the background.

Because the interactive REPL requires your terminal's standard input/output, the embedded FastMCP server defaults to using the **SSE (Server-Sent Events) transport** over HTTP.

You will see a startup message like:

```
[SYSTEM] Embedded FastMCP server running at http://127.0.0.1:8000/sse
```

If MCP tools exist but FastMCP is not installed, Brimley continues running REPL and logs a non-fatal warning.

You can now point your MCP-compatible LLM client to `http://127.0.0.1:8000/sse` to allow the LLM to call your Brimley functions in real-time while you monitor or interact with the REPL.

Embedded runtime settings are configured in `brimley.yaml`:

```
mcp:
  embedded: true
  transport: sse
  host: 127.0.0.1
  port: 8000
```

When watch mode or `/reload` applies a successful registry update, Brimley refreshes embedded MCP tool registrations. If FastMCP is missing, Brimley emits a warning and continues running without failing the REPL session.

## Embedding Brimley MCP in External Apps (LangGraph, etc.)

Long-term, you may not want to run the Brimley REPL, but rather embed Brimley's functions directly into an existing AI framework (like LangGraph) or an existing FastMCP server.

Brimley provides an adapter for this exact use case:

```
from pathlib import Path

from brimley.config.loader import load_config
from brimley.core.context import BrimleyContext
from brimley.discovery.scanner import Scanner
from brimley.mcp.adapter import BrimleyMCPAdapter

# 1. Load your Brimley environment
root_dir = Path(".")
config = load_config(root_dir / "brimley.yaml")
context = BrimleyContext(config_dict=config)

scan_result = Scanner(root_dir).scan()
context.functions.register_all(scan_result.functions)

# 2. Initialize the Adapter
adapter = BrimleyMCPAdapter(context.functions, context)

# 3. Create a FastMCP instance and register tools
mcp_server = adapter.register_tools()

# 4. Run it standalone
mcp_server.run(transport="sse", host="127.0.0.1", port=8000)

# Optional: register on an existing FastMCP server
# adapter.register_tools(mcp_server=existing_server)
```

For a runnable script version, see `examples/mcp_external_embedding.py`.

## Host-Managed Auto Reload for External Servers

For non-REPL hosting, use `BrimleyRuntimeController` to watch files and refresh tool registrations in your app lifecycle.

```python
from pathlib import Path

from brimley.runtime import BrimleyRuntimeController
from brimley.runtime.mcp_refresh_adapter import ExternalMCPRefreshAdapter

runtime = BrimleyRuntimeController(root_dir=Path("."))
runtime.load_initial()

refresh_adapter = ExternalMCPRefreshAdapter(
  context=runtime.context,
  get_server=lambda: current_server,
  set_server=lambda server: set_current_server(server),
)

runtime.mcp_refresh = refresh_adapter.refresh
runtime.start_auto_reload(background=True)
```

This keeps external-host MCP tools aligned with Brimley function changes while preserving existing runtime domains when reload failures occur.