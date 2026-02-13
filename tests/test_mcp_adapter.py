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
