from typing import Any

from brimley.core.context import BrimleyContext
from brimley.core.models import BrimleyFunction
from brimley.core.registry import Registry


class BrimleyMCPAdapter:
    """
    Adapter scaffold for exposing Brimley functions through MCP.
    """

    def __init__(self, registry: Registry[BrimleyFunction], context: BrimleyContext):
        """
        Initialize the adapter with function registry and runtime context.
        """
        self.registry = registry
        self.context = context

    def register_tools(self, mcp_server: Any = None) -> Any:
        """
        Register MCP-compatible tools on a server instance.

        This is a scaffold for M2.2+ and intentionally no-ops for now.
        """
        return mcp_server
