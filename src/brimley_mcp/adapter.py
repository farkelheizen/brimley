from typing import Any, Dict

# Placeholder for Brimley -> FastMCP Adapter
# Will be implemented in Phase 2

class BrimleyMCPAdapter:
    """
    Adapts BrimleyEngine tools into FastMCP compatible tool definitions.
    """
    def __init__(self, brimley_engine, mcp_server):
        self.engine = brimley_engine
        self.mcp = mcp_server

    def register_tools(self):
        """
        Iterates through Brimley tools and registers them with the MCP server.
        """
        pass
