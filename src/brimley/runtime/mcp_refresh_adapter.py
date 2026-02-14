from __future__ import annotations

from typing import Any, Callable, Optional

from brimley.core.context import BrimleyContext
from brimley.mcp.adapter import BrimleyMCPAdapter


class ExternalMCPRefreshAdapter:
    """Refresh adapter for host-managed FastMCP server lifecycles."""

    def __init__(
        self,
        context: BrimleyContext,
        get_server: Callable[[], Any | None],
        set_server: Callable[[Any], None],
        server_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Initialize external refresh adapter.

        Args:
            context: Active runtime context that contains function registry.
            get_server: Host callback returning current MCP server instance.
            set_server: Host callback for replacing MCP server instance.
            server_factory: Optional host callback to create a fresh server instance.
        """

        self.context = context
        self.get_server = get_server
        self.set_server = set_server
        self.server_factory = server_factory

    def refresh(self) -> Any | None:
        """Refresh MCP tools for the external host server and return active server.

        Strategy order:
        1. If no current server, create/register tools via Brimley adapter.
        2. If server supports tool reset (`clear_tools` or `reset_tools`), refresh in place.
        3. If server cannot reset but `server_factory` is provided, create and swap server.
        4. Fallback: register tools onto existing server (best effort).
        """

        adapter = BrimleyMCPAdapter(registry=self.context.functions, context=self.context)
        current_server = self.get_server()

        if current_server is None:
            next_server = adapter.register_tools()
            if next_server is not None:
                self.set_server(next_server)
            return next_server

        if self._supports_clear_tools(current_server):
            self._clear_tools(current_server)
            refreshed = adapter.register_tools(mcp_server=current_server)
            if refreshed is not None:
                self.set_server(refreshed)
            return refreshed

        if self.server_factory is not None:
            next_server = self.server_factory()
            refreshed = adapter.register_tools(mcp_server=next_server)
            if refreshed is not None:
                self.set_server(refreshed)
            return refreshed

        refreshed = adapter.register_tools(mcp_server=current_server)
        if refreshed is not None:
            self.set_server(refreshed)
        return refreshed

    def _supports_clear_tools(self, server: Any) -> bool:
        return callable(getattr(server, "clear_tools", None)) or callable(getattr(server, "reset_tools", None))

    def _clear_tools(self, server: Any) -> None:
        clear_tools = getattr(server, "clear_tools", None)
        if callable(clear_tools):
            clear_tools()
            return

        reset_tools = getattr(server, "reset_tools", None)
        if callable(reset_tools):
            reset_tools()
