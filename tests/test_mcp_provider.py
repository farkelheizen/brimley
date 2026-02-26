from brimley.core.context import BrimleyContext
from brimley.core.models import SqlFunction, TemplateFunction
from brimley.core.registry import Registry
from brimley.infrastructure.database import initialize_databases
from brimley.mcp.adapter import BrimleyMCPAdapter
from brimley.mcp.fastmcp_provider import BrimleyProvider


class _FakeMCPServer:
    def __init__(self):
        self.tools = []

    def add_tool(self, tool):
        self.tools.append(tool)


def test_provider_stores_registry_and_context():
    context = BrimleyContext()
    provider = BrimleyProvider(registry=context.functions, context=context)

    assert provider.registry is context.functions
    assert provider.context is context


def test_provider_discovers_only_mcp_tools():
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

    provider = BrimleyProvider(registry=context.functions, context=context)
    tools = provider.discover_tools()

    assert [tool.name for tool in tools] == ["hello_tool"]


def test_adapter_is_provider_compatibility_shim():
    assert issubclass(BrimleyMCPAdapter, BrimleyProvider)


def test_tool_wrapper_late_binds_template_function_after_registry_reload():
    context = BrimleyContext()
    initial_func = TemplateFunction(
        name="hello_tool",
        type="template_function",
        return_shape="string",
        template_body="Hello V1 {{ args.name }}",
        mcp={"type": "tool"},
        arguments={"inline": {"name": {"type": "string"}}},
    )
    context.functions.register(initial_func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    wrapper = provider.create_tool_wrapper(initial_func)

    assert wrapper(name="Dev") == "Hello V1 Dev"

    next_registry: Registry[TemplateFunction] = Registry()
    next_registry.register(
        TemplateFunction(
            name="hello_tool",
            type="template_function",
            return_shape="string",
            template_body="Hello V2 {{ args.name }}",
            mcp={"type": "tool"},
            arguments={"inline": {"name": {"type": "string"}}},
        )
    )
    context.functions = next_registry

    assert wrapper(name="Dev") == "Hello V2 Dev"


def test_tool_wrapper_late_binds_sql_function_after_registry_reload(tmp_path):
    context = BrimleyContext(
        config_dict={
            "databases": {
                "default": {
                    "url": f"sqlite:///{tmp_path / 'provider_reload.db'}",
                }
            }
        }
    )
    context.databases = initialize_databases(context.databases)

    initial_func = SqlFunction(
        name="get_users",
        type="sql_function",
        return_shape="list[dict]",
        sql_body="SELECT 'V1' as version",
        mcp={"type": "tool"},
    )
    context.functions.register(initial_func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    wrapper = provider.create_tool_wrapper(initial_func)

    assert wrapper() == [{"version": "V1"}]

    next_registry: Registry[SqlFunction] = Registry()
    next_registry.register(
        SqlFunction(
            name="get_users",
            type="sql_function",
            return_shape="list[dict]",
            sql_body="SELECT 'V2' as version",
            mcp={"type": "tool"},
        )
    )
    context.functions = next_registry

    assert wrapper() == [{"version": "V2"}]
