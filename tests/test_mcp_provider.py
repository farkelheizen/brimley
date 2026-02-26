from brimley.core.context import BrimleyContext
from brimley.core.models import TemplateFunction
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
