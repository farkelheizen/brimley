from __future__ import annotations

from typing import Any, Callable, Optional

from brimley.core.context import BrimleyContext
from brimley.mcp.fastmcp_provider import BrimleyProvider


class ProviderMCPRefreshManager:
    """Canonical provider-led refresh manager for host-managed FastMCP lifecycles."""

    def __init__(
        self,
        context: BrimleyContext,
        get_server: Callable[[], Any | None],
        set_server: Callable[[Any], None],
        server_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Initialize provider refresh manager.

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
        self._schema_signatures: dict[str, str] = {}

    def refresh(self) -> Any | None:
        """Refresh MCP tools for the external host server and return active server.

        Strategy order:
        1. If no current server, create/register tools via Brimley provider.
        2. If server supports tool reset (`clear_tools` or `reset_tools`), refresh in place.
        3. If server cannot reset but `server_factory` is provided, create and swap server.
        4. Fallback: register tools onto existing server (best effort).
        """

        adapter = BrimleyProvider(registry=self.context.functions, context=self.context)
        tools = adapter.discover_tools()
        schema_signatures = adapter.get_tool_schema_signatures(tools)
        current_server = self.get_server()

        if not tools:
            self._schema_signatures = {}
            return current_server

        if not adapter.is_fastmcp_available():
            raise RuntimeError("MCP tools found but 'fastmcp' is not installed. Install with: pip install fastmcp")

        if current_server is None:
            next_server = adapter.register_tools()
            if next_server is not None:
                self.set_server(next_server)
            self._schema_signatures = schema_signatures
            return next_server

        if self._schema_signatures and schema_signatures != self._schema_signatures:
            if self.server_factory is None:
                raise RuntimeError(
                    "client_action_required: MCP tool schema changed; restart or reinitialize provider to apply schema updates"
                )

            next_server = self.server_factory()
            refreshed = adapter.register_tools(mcp_server=next_server)
            if refreshed is not None:
                self.set_server(refreshed)
            self._schema_signatures = schema_signatures
            return refreshed

        if self._supports_clear_tools(current_server):
            self._clear_tools(current_server)
            refreshed = adapter.register_tools(mcp_server=current_server)
            if refreshed is not None:
                self.set_server(refreshed)
            self._schema_signatures = schema_signatures
            return refreshed

        if self.server_factory is not None:
            next_server = self.server_factory()
            refreshed = adapter.register_tools(mcp_server=next_server)
            if refreshed is not None:
                self.set_server(refreshed)
            self._schema_signatures = schema_signatures
            return refreshed

        refreshed = adapter.register_tools(mcp_server=current_server)
        if refreshed is not None:
            self.set_server(refreshed)
        self._schema_signatures = schema_signatures
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


class ExternalMCPRefreshAdapter(ProviderMCPRefreshManager):
    """Compatibility shim for legacy adapter naming; provider manager is canonical."""
