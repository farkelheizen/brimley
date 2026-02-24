# Model Context Protocol (MCP) Integration

> Version 0.4

Brimley acts as a powerful single source of truth for your organizational functions. With built-in support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/ "null"), you can seamlessly expose your Brimley functions as tools to Large Language Models (LLMs) and agents like Claude, LangGraph, or AutoGen.

Under the hood, Brimley uses [FastMCP](https://github.com/PrefectHQ/fastmcp) to create and host these tools.

FastMCP is optional at install time. Brimley only requires it when you actually register or run MCP tools.

## Exposing a Function as an MCP Tool

For Python functions, expose tools with the decorator option `mcpType="tool"`.

```python
from typing import Annotated
from brimley import function, Config

@function(name="create_user", mcpType="tool")
def create_user(
    username: str,
    role: str = "viewer",
    support_email: Annotated[str, Config("support_email")] = "",
) -> dict:
    return {
        "username": username,
        "role": role,
        "created_by": support_email,
    }
```

### Argument Filtering (Smart Context)

When Brimley exposes a function via MCP, it **intelligently filters the tool signature**. LLMs do not know about your internal configuration, secrets, or context variables.

In the example above:

- The LLM will **only** be prompted to provide the `username` and `role` arguments.
    
- The `support_email` argument (sourced from `from_context`) is hidden from the LLM's schema entirely.
    
- When the LLM calls the tool, Brimley intercepts the call, fetches `config.support_email` from the active `BrimleyContext`, injects it, and executes the function seamlessly.

### Agentic Python Tools (Context Passthrough)

For Python tools, Brimley passes FastMCP invocation context through the MCP adapter into runtime injections. This allows handlers to declare `mcp.server.fastmcp.Context` directly in their function signature.

```python
from brimley import function
from brimley.core.context import BrimleyContext
from mcp.server.fastmcp import Context

@function(mcpType="tool")
def agent_tool(prompt: str, ctx: BrimleyContext, mcp_ctx: Context):
    sample = mcp_ctx.session.sample(messages=[{"role": "user", "content": prompt}])
    return {
      "prompt": prompt,
      "sample": sample.message.content[0].text,
      "functions_loaded": len(ctx.functions),
    }
```

Brimley also keeps these system parameters out of exposed tool schemas, so LLM clients only provide true business arguments.

Python MCP tools can also compose other Brimley functions by name through `BrimleyContext`:

```python
from brimley import function
from brimley.core.context import BrimleyContext
from mcp.server.fastmcp import Context

@function(mcpType="tool")
def orchestrator_tool(prompt: str, ctx: BrimleyContext, mcp_ctx: Context):
  sampled = mcp_ctx.session.sample(messages=[{"role": "user", "content": prompt}])
  return ctx.execute_function_by_name(
    function_name="post_process_summary",
    input_data={"text": sampled.message.content[0].text},
    runtime_injections={"mcp_context": mcp_ctx},
  )
```

This preserves normal nested invocation semantics (lookup, argument resolution, dispatch) while still allowing MCP context passthrough for downstream Python handlers that request `Context`.
    

## The Embedded REPL Server

When you start the Brimley REPL via the CLI (`brimley repl`), Brimley discovers all functions exposed as MCP tools (for Python this is typically `@function(mcpType="tool")`). If any are found and MCP embedding is enabled (`mcp.embedded: true`, or via CLI override), Brimley spins up an embedded FastMCP server in the background.

Because the interactive REPL requires your terminal's standard input/output, the embedded FastMCP server defaults to using the **SSE (Server-Sent Events) transport** over HTTP.

You will see a startup message like:

```
[SYSTEM] Embedded FastMCP server running at http://127.0.0.1:8000/sse
```

If MCP tools exist but FastMCP is not installed, Brimley continues running REPL and logs a non-fatal warning.

In REPL mode, Brimley also creates a local `MockMCPContext` shim and passes it to runtime injections for function execution. Calls to `session.sample(...)` are printed as `[Mock Sampling]` and return deterministic dummy responses, enabling local agentic-tool development without a live MCP server or model backend.

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

### Schema-Shape Change Semantics (v0.4)

- Logic-only changes can refresh wrappers/tool behavior without requiring schema rebuild.

- If an MCP-exposed function signature shape changes (argument names/types/defaults/requiredness), the tool schema must be rebuilt and clients must reconnect to consume the new schema.

- Embedded REPL hosting restarts/reinitializes MCP provider lifecycle for schema-shape changes rather than silently hot-applying stale schema.

- External host-managed refresh uses provider reinitialization when available; if no reinit path is available, Brimley raises a `client_action_required` error indicating restart/reconnect is required.

## Running MCP Without REPL (CLI)

Use the first-class MCP server command:

```
brimley mcp-serve --root .
```

Enable watch mode:

```
brimley mcp-serve --root . --watch
```

Optional bind overrides:

```
brimley mcp-serve --root . --host 127.0.0.1 --port 8000
```

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

Minimal embedding snippet:

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