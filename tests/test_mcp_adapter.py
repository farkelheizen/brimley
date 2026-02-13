from brimley.core.context import BrimleyContext
from brimley.core.models import TemplateFunction
from brimley.mcp.adapter import BrimleyMCPAdapter


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
