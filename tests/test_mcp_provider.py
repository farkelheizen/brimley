from brimley.core.context import BrimleyContext
from brimley.core.models import PythonFunction, SqlFunction, TemplateFunction
from brimley.core.registry import Registry
from brimley.infrastructure.database import initialize_databases
from brimley.mcp.adapter import BrimleyMCPAdapter
from brimley.mcp.fastmcp_provider import BrimleyProvider
import inspect
import pytest


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


@pytest.mark.anyio
async def test_python_tool_wrapper_is_async_and_awaits_dispatcher_result():
    context = BrimleyContext()
    func = PythonFunction(
        name="agent_tool",
        type="python_function",
        return_shape="string",
        handler="examples.agent_sample.agent_sample",
        mcp={"type": "tool"},
        arguments={"inline": {"prompt": {"type": "string"}}},
    )
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    wrapper = provider.create_tool_wrapper(func)

    assert inspect.iscoroutinefunction(wrapper)

    captured: dict[str, object] = {}

    async def fake_execute(function_name, tool_args, runtime_injections=None):
        captured["function_name"] = function_name
        captured["tool_args"] = tool_args
        captured["runtime_injections"] = runtime_injections
        return "async-ok"

    provider.execute_tool_by_name = fake_execute  # type: ignore[method-assign]

    mcp_ctx = object()
    result = await wrapper(prompt="hello", ctx=mcp_ctx)

    assert result == "async-ok"
    assert captured["function_name"] == "agent_tool"
    assert captured["tool_args"] == {"prompt": "hello"}
    assert captured["runtime_injections"] == {"mcp_context": mcp_ctx}
