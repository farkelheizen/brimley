from brimley.core.context import BrimleyContext
from brimley.core.models import TemplateFunction
from brimley.mcp.adapter import BrimleyMCPAdapter


class _FakeMCPServer:
    def __init__(self):
        self.tools = []

    def add_tool(self, tool):
        self.tools.append(tool)


def test_mcp_adapter_stores_registry_and_context():
    context = BrimleyContext()
    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    assert adapter.registry is context.functions
    assert adapter.context is context


def test_mcp_adapter_construction_with_registered_function():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="hello",
            type="template_function",
            return_shape="string",
            template_body="Hello",
        )
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    assert len(list(adapter.registry)) == 1
    assert adapter.registry.get("hello").name == "hello"


def test_discover_tools_filters_only_mcp_tool_functions():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="hello_tool",
            type="template_function",
            return_shape="string",
            template_body="Hello",
            mcp={"type": "tool"},
        )
    )
    context.functions.register(
        TemplateFunction(
            name="hello_internal",
            type="template_function",
            return_shape="string",
            template_body="Hello",
        )
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)
    tools = adapter.discover_tools()

    assert [tool.name for tool in tools] == ["hello_tool"]


def test_build_tool_input_model_excludes_from_context_arguments():
    context = BrimleyContext()
    func = TemplateFunction(
        name="hello",
        type="template_function",
        return_shape="string",
        template_body="Hello",
        mcp={"type": "tool"},
        arguments={
            "inline": {
                "name": {"type": "string"},
                "count": {"type": "int", "default": 1},
                "support_email": {"type": "string", "from_context": "config.support_email"},
            }
        },
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)
    input_model = adapter.build_tool_input_model(func)

    assert "name" in input_model.model_fields
    assert "count" in input_model.model_fields
    assert "support_email" not in input_model.model_fields
    assert input_model.model_fields["name"].is_required()
    assert not input_model.model_fields["count"].is_required()
    assert input_model.model_fields["count"].default == 1


def test_create_tool_wrapper_executes_through_dispatcher_with_context_injection():
    context = BrimleyContext(config_dict={"config": {"support_email": "support@example.com"}})
    func = TemplateFunction(
        name="hello",
        type="template_function",
        return_shape="string",
        template_body="Hello {{ args.name }} - {{ args.support_email }}",
        mcp={"type": "tool"},
        arguments={
            "inline": {
                "name": {"type": "string"},
                "support_email": {"type": "string", "from_context": "config.support_email"},
            }
        },
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)
    wrapper = adapter.create_tool_wrapper(func)

    result = wrapper(name="Developer")

    assert "Hello Developer" in result
    assert "support@example.com" in result


def test_create_tool_wrapper_applies_default_arguments():
    context = BrimleyContext()
    func = TemplateFunction(
        name="hello_default",
        type="template_function",
        return_shape="string",
        template_body="Hello {{ args.name }}",
        mcp={"type": "tool"},
        arguments={
            "inline": {
                "name": {"type": "string", "default": "World"},
            }
        },
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)
    wrapper = adapter.create_tool_wrapper(func)

    result = wrapper()

    assert result == "Hello World"


def test_is_fastmcp_available_true_when_spec_exists(monkeypatch):
    context = BrimleyContext()
    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    monkeypatch.setattr("brimley.mcp.adapter.importlib.util.find_spec", lambda _: object())

    assert adapter.is_fastmcp_available() is True


def test_is_fastmcp_available_false_when_spec_missing(monkeypatch):
    context = BrimleyContext()
    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    monkeypatch.setattr("brimley.mcp.adapter.importlib.util.find_spec", lambda _: None)

    assert adapter.is_fastmcp_available() is False


def test_require_fastmcp_raises_clear_error_when_missing(monkeypatch):
    context = BrimleyContext()
    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    monkeypatch.setattr("brimley.mcp.adapter.importlib.util.find_spec", lambda _: None)

    try:
        adapter.require_fastmcp()
        assert False, "Expected RuntimeError when fastmcp is unavailable"
    except RuntimeError as exc:
        assert "fastmcp" in str(exc)
        assert "pip install" in str(exc)


def test_require_fastmcp_returns_class_when_available(monkeypatch):
    class FakeFastMCP:
        pass

    class FakeModule:
        FastMCP = FakeFastMCP

    context = BrimleyContext()
    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    monkeypatch.setattr("brimley.mcp.adapter.importlib.util.find_spec", lambda _: object())
    monkeypatch.setattr("brimley.mcp.adapter.importlib.import_module", lambda _: FakeModule())

    resolved = adapter.require_fastmcp()
    assert resolved is FakeFastMCP


def test_register_tools_uses_supplied_external_server():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="hello_tool",
            type="template_function",
            return_shape="string",
            template_body="Hello",
            mcp={"type": "tool"},
        )
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)
    server = _FakeMCPServer()

    returned = adapter.register_tools(server)

    assert returned is server
    assert len(server.tools) == 1
    assert server.tools[0].__name__ == "hello_tool"


def test_register_tools_noop_when_no_mcp_tools():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="hello_internal",
            type="template_function",
            return_shape="string",
            template_body="Hello",
        )
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)
    server = _FakeMCPServer()

    returned = adapter.register_tools(server)

    assert returned is server
    assert server.tools == []


def test_register_tools_raises_value_error_on_tool_registration_failure():
    class FailingServer:
        def add_tool(self, tool):
            raise ValueError("duplicate tool")

    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="hello_tool",
            type="template_function",
            return_shape="string",
            template_body="Hello",
            mcp={"type": "tool"},
        )
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    try:
        adapter.register_tools(FailingServer())
        assert False, "Expected ValueError when MCP tool registration fails"
    except ValueError as exc:
        assert "hello_tool" in str(exc)
        assert "duplicate tool" in str(exc)


def test_register_tools_raises_value_error_for_invalid_server_shape():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="hello_tool",
            type="template_function",
            return_shape="string",
            template_body="Hello",
            mcp={"type": "tool"},
        )
    )

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)

    try:
        adapter.register_tools(object())
        assert False, "Expected ValueError for invalid MCP server"
    except ValueError as exc:
        assert "MCP server" in str(exc)
