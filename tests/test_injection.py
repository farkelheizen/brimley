from typing import Any

from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from brimley.core.models import PythonFunction
from brimley.execution.arguments import ArgumentResolver
from brimley.execution.dispatcher import Dispatcher
from brimley.execution import execute_helper
from brimley.mcp.mock import MockMCPContext


class MockPythonRunnerDispatcher(Dispatcher):
    def __init__(self, handler_map: dict[str, Any]):
        super().__init__()
        self.handler_map = handler_map

        def _load_handler(handler_path: str):
            return self.handler_map[handler_path]

        self.python_runner._load_handler = _load_handler  # type: ignore[method-assign]


class UserPayload(Entity):
    value: int
    tag: str


def test_injection_brimley_context_via_dispatcher_python_runner() -> None:
    context = BrimleyContext()

    def handler(name: str, ctx: BrimleyContext) -> dict[str, Any]:
        return {
            "name": name,
            "ctx_id": id(ctx),
            "app_name": ctx.settings.app_name,
        }

    dispatcher = MockPythonRunnerDispatcher({"test.handlers.context_injection": handler})

    func = PythonFunction(
        name="context_injection",
        type="python_function",
        return_shape="dict",
        handler="test.handlers.context_injection",
    )

    result = dispatcher.run(func, {"name": "Alice"}, context)

    assert result["name"] == "Alice"
    assert result["ctx_id"] == id(context)
    assert result["app_name"] == context.settings.app_name


def test_injection_mock_mcp_with_entity_and_from_context_resolution() -> None:
    context = BrimleyContext(config_dict={"config": {"support_email": "support@example.com"}})
    mock_mcp_context = MockMCPContext(response_text="local mock sample")

    FastMCPContext = type("Context", (), {"__module__": "mcp.server.fastmcp"})

    def handler(
        payload: UserPayload,
        request_id: str,
        support_email: str,
        ctx: BrimleyContext,
        mcp_ctx: FastMCPContext,
    ) -> dict[str, Any]:
        sample_result = mcp_ctx.session.sample(messages=[{"role": "user", "content": "ping"}])
        return {
            "request_id": request_id,
            "payload_tag": payload.tag,
            "payload_value": payload.value,
            "support_email": support_email,
            "ctx_id": id(ctx),
            "mcp_ctx_id": id(mcp_ctx),
            "sample_text": sample_result.message.content[0].text,
        }

    dispatcher = MockPythonRunnerDispatcher({"test.handlers.full_injection": handler})

    func = PythonFunction(
        name="full_injection",
        type="python_function",
        return_shape="dict",
        handler="test.handlers.full_injection",
        arguments={
            "inline": {
                "payload": {"type": "UserPayload"},
                "request_id": {"type": "string"},
                "support_email": {"type": "string", "from_context": "config.support_email"},
            }
        },
    )

    user_input = {
        "payload": UserPayload(value=7, tag="alpha"),
        "request_id": "req-123",
    }

    resolved_args = ArgumentResolver.resolve(func, user_input, context)

    result = dispatcher.run(
        func,
        resolved_args,
        context,
        runtime_injections={"mcp_context": mock_mcp_context},
    )

    assert result["request_id"] == "req-123"
    assert result["payload_tag"] == "alpha"
    assert result["payload_value"] == 7
    assert result["support_email"] == "support@example.com"
    assert result["ctx_id"] == id(context)
    assert result["mcp_ctx_id"] == id(mock_mcp_context)
    assert result["sample_text"] == "local mock sample"


def test_nested_invoke_helper_preserves_context_and_mcp_injection(
    monkeypatch,
) -> None:
    context = BrimleyContext()
    mock_mcp_context = MockMCPContext(response_text="nested mock sample")

    FastMCPContext = type("Context", (), {"__module__": "mcp.server.fastmcp"})

    def nested_handler(request_id: str, ctx: BrimleyContext, mcp_ctx: FastMCPContext) -> dict[str, Any]:
        sample_result = mcp_ctx.session.sample(messages=[{"role": "user", "content": "nested"}])
        return {
            "request_id": request_id,
            "ctx_id": id(ctx),
            "mcp_ctx_id": id(mcp_ctx),
            "sample_text": sample_result.message.content[0].text,
        }

    class HelperDispatcher(MockPythonRunnerDispatcher):
        def __init__(self):
            super().__init__({"test.handlers.nested": nested_handler})

    nested_func = PythonFunction(
        name="nested_injected",
        type="python_function",
        return_shape="dict",
        handler="test.handlers.nested",
        arguments={"inline": {"request_id": "string"}},
    )
    context.functions.register(nested_func)

    monkeypatch.setattr(execute_helper, "Dispatcher", HelperDispatcher)

    result = execute_helper.execute_function_by_name(
        context=context,
        function_name="nested_injected",
        input_data={"request_id": "nested-1"},
        runtime_injections={"mcp_context": mock_mcp_context},
    )

    assert result["request_id"] == "nested-1"
    assert result["ctx_id"] == id(context)
    assert result["mcp_ctx_id"] == id(mock_mcp_context)
    assert result["sample_text"] == "nested mock sample"
