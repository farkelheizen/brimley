import pytest

from brimley.core.context import BrimleyContext
from brimley.core.models import TemplateFunction
from brimley.runtime.mcp_refresh_adapter import ExternalMCPRefreshAdapter, ProviderMCPRefreshManager


class _HostServer:
    def __init__(self) -> None:
        self.tools = []

    def add_tool(self, tool):
        self.tools.append(tool)


class _HostServerWithClear(_HostServer):
    def __init__(self) -> None:
        super().__init__()
        self.clear_calls = 0

    def clear_tools(self) -> None:
        self.clear_calls += 1
        self.tools = []


def _register_tool_function(context: BrimleyContext, name: str = "hello_tool") -> None:
    context.functions.register(
        TemplateFunction(
            name=name,
            type="template_function",
            return_shape="string",
            template_body="Hello",
            mcp={"type": "tool"},
        )
    )


def _mock_fastmcp(monkeypatch) -> None:
    class FakeTool:
        def __init__(self, name=None, description=None, fn=None, parameters=None):
            self.name = name
            self.key = name
            self.description = description
            self.fn = fn
            self.parameters = parameters or {}

        @classmethod
        def from_function(cls, fn, name=None, description=None, **kwargs):
            return cls(name=name, description=description, fn=fn, parameters={})

    class FakeToolsModule:
        Tool = FakeTool

    class FakeFastMCP:
        def __init__(self, name=None):
            self.name = name
            self.tools = []

        def add_tool(self, tool):
            self.tools.append(tool)

    class FakeModule:
        tools = FakeToolsModule
        FastMCP = FakeFastMCP

    monkeypatch.setattr("brimley.mcp.fastmcp_provider.importlib.util.find_spec", lambda _: object())
    monkeypatch.setattr("brimley.mcp.fastmcp_provider.importlib.import_module", lambda name: FakeModule() if name == "fastmcp" else __import__(name))


def test_external_mcp_refresh_creates_server_when_missing(monkeypatch):
    _mock_fastmcp(monkeypatch)

    context = BrimleyContext()
    _register_tool_function(context)

    state = {"server": None}

    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda server: state.__setitem__("server", server),
    )

    refreshed = adapter.refresh()

    assert refreshed is not None
    assert state["server"] is refreshed


def test_external_mcp_refresh_clears_tools_when_server_supports_it(monkeypatch):
    _mock_fastmcp(monkeypatch)

    context = BrimleyContext()
    _register_tool_function(context)

    server = _HostServerWithClear()
    server.tools.append(object())

    state = {"server": server}

    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda next_server: state.__setitem__("server", next_server),
    )

    refreshed = adapter.refresh()

    assert refreshed is server
    assert server.clear_calls == 1
    assert len(server.tools) == 1


def test_external_mcp_refresh_uses_factory_when_server_cannot_clear(monkeypatch):
    _mock_fastmcp(monkeypatch)

    context = BrimleyContext()
    _register_tool_function(context)

    first_server = _HostServer()
    second_server = _HostServer()

    state = {"server": first_server}

    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda next_server: state.__setitem__("server", next_server),
        server_factory=lambda: second_server,
    )

    refreshed = adapter.refresh()

    assert refreshed is second_server
    assert state["server"] is second_server
    assert len(second_server.tools) == 1


def test_external_mcp_refresh_falls_back_to_register_on_existing_server(monkeypatch):
    _mock_fastmcp(monkeypatch)

    context = BrimleyContext()
    _register_tool_function(context)

    server = _HostServer()
    state = {"server": server}

    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda next_server: state.__setitem__("server", next_server),
    )

    refreshed = adapter.refresh()

    assert refreshed is server
    assert state["server"] is server
    assert len(server.tools) == 1


def test_external_mcp_refresh_raises_clear_error_when_fastmcp_missing(monkeypatch):
    monkeypatch.setattr("brimley.mcp.fastmcp_provider.importlib.util.find_spec", lambda _: None)

    context = BrimleyContext()
    _register_tool_function(context)

    state = {"server": None}
    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda next_server: state.__setitem__("server", next_server),
    )

    with pytest.raises(RuntimeError) as exc_info:
        adapter.refresh()

    assert "fastmcp" in str(exc_info.value).lower()
    assert state["server"] is None


def test_external_mcp_refresh_noops_without_tools_even_if_fastmcp_missing(monkeypatch):
    monkeypatch.setattr("brimley.mcp.fastmcp_provider.importlib.util.find_spec", lambda _: None)

    context = BrimleyContext()
    state = {"server": _HostServer()}

    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda next_server: state.__setitem__("server", next_server),
    )

    refreshed = adapter.refresh()

    assert refreshed is state["server"]
    assert state["server"].tools == []


def test_external_mcp_refresh_reinitializes_server_on_schema_change(monkeypatch):
    _mock_fastmcp(monkeypatch)

    context = BrimleyContext()
    _register_tool_function(context)
    tool_func = context.functions.get("hello_tool")
    tool_func.arguments = {"inline": {"name": {"type": "string", "default": "world"}}}

    first_server = _HostServerWithClear()
    second_server = _HostServer()
    state = {"server": first_server}

    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda next_server: state.__setitem__("server", next_server),
        server_factory=lambda: second_server,
    )

    initial = adapter.refresh()
    assert initial is first_server

    tool_func.arguments = {"inline": {"name": {"type": "string", "default": "developer"}}}
    refreshed = adapter.refresh()

    assert refreshed is second_server
    assert state["server"] is second_server
    assert first_server.clear_calls == 1
    assert len(second_server.tools) == 1


def test_external_mcp_refresh_raises_client_action_required_when_schema_changes_without_reinit_path(monkeypatch):
    _mock_fastmcp(monkeypatch)

    context = BrimleyContext()
    _register_tool_function(context)
    tool_func = context.functions.get("hello_tool")
    tool_func.arguments = {"inline": {"name": {"type": "string", "default": "world"}}}

    server = _HostServerWithClear()
    state = {"server": server}

    adapter = ExternalMCPRefreshAdapter(
        context=context,
        get_server=lambda: state["server"],
        set_server=lambda next_server: state.__setitem__("server", next_server),
    )

    adapter.refresh()
    tool_func.arguments = {"inline": {"name": {"type": "string", "default": "developer"}}}

    with pytest.raises(RuntimeError) as exc_info:
        adapter.refresh()

    assert "client_action_required" in str(exc_info.value)


def test_external_refresh_adapter_is_compatibility_shim():
    assert issubclass(ExternalMCPRefreshAdapter, ProviderMCPRefreshManager)
