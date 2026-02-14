from pathlib import Path
from typing import Any

from brimley.config.loader import load_config
from brimley.core.context import BrimleyContext
from brimley.discovery.scanner import Scanner
from brimley.mcp.adapter import BrimleyMCPAdapter


def build_mcp_server(root_dir: Path) -> Any:
    """Build a FastMCP server populated with Brimley MCP tools."""
    config_data = load_config(root_dir / "brimley.yaml")
    context = BrimleyContext(config_dict=config_data)

    scan_result = Scanner(root_dir).scan()
    context.functions.register_all(scan_result.functions)

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    # Option A: Create and return a new FastMCP server instance
    return adapter.register_tools()


def register_on_existing_server(root_dir: Path, server: Any) -> Any:
    """Register Brimley MCP tools on an existing FastMCP server."""
    config_data = load_config(root_dir / "brimley.yaml")
    context = BrimleyContext(config_dict=config_data)

    scan_result = Scanner(root_dir).scan()
    context.functions.register_all(scan_result.functions)

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    # Option B: Attach Brimley tools to your pre-existing FastMCP server
    return adapter.register_tools(mcp_server=server)


def main() -> None:
    root_dir = Path(__file__).parent

    try:
        mcp_server = build_mcp_server(root_dir)
    except RuntimeError as exc:
        print(exc)
        print("Install FastMCP to run this example: pip install fastmcp")
        return

    if mcp_server is None:
        print("No MCP tools discovered (add mcp: { type: tool } in frontmatter).")
        return

    print("Serving Brimley MCP tools on http://127.0.0.1:8000/sse")
    mcp_server.run(transport="sse", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
