import sys
import types

import pytest

from typing import Any

from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from brimley.core.models import PythonFunction
from brimley.execution.arguments import ArgumentResolver
from brimley.execution.dispatcher import Dispatcher
from brimley.execution import execute_helper
from brimley.mcp.mock import MockMCPContext
from brimley.core.container import BrimleyContainer
from brimley.core.di import Depends
from brimley.core.models import ProviderMetadata
from brimley.utils.diagnostics import BrimleyExecutionError


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


# ---------------------------------------------------------------------------
# B08-S8: Depends() injection
# ---------------------------------------------------------------------------


def _make_module(name: str, **attrs: Any) -> types.ModuleType:
    mod = types.ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(mod, attr_name, value)
    sys.modules[name] = mod
    return mod


def _register_provider(
    container: BrimleyContainer,
    module_name: str,
    func_name: str,
    fn: Any,
    scope: str = "singleton",
    provider_name: str | None = None,
) -> None:
    _make_module(module_name, **{func_name: fn})
    meta = ProviderMetadata(
        name=provider_name,
        module_path=module_name,
        func_name=func_name,
        handler=f"{module_name}.{func_name}",
        scope=scope,
        eager=False,
    )
    container.register(meta)


class _DepsMockDispatcher(Dispatcher):
    """Dispatcher that injects a custom handler without filesystem module loading."""

    def __init__(self, handler: Any) -> None:
        super().__init__()
        self._stub = handler
        self.python_runner._load_handler = lambda _path, **_kw: self._stub  # type: ignore[method-assign]


def test_depends_basic_injection() -> None:
    """A Depends() parameter is resolved from the container and injected."""
    def get_service() -> str:
        return "resolved-service"

    container = BrimleyContainer()
    _register_provider(container, "_t.inj_basic", "get_service", get_service, provider_name="get_service")
    context = BrimleyContext()
    context.container = container

    def handler(name: str, svc: str = Depends(get_service)) -> dict:
        return {"name": name, "svc": svc}

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="basic_depends",
        type="python_function",
        return_shape="dict",
        handler="test.basic.handler",
    )
    result = dispatcher.run(func, {"name": "Alice"}, context)

    assert result["name"] == "Alice"
    assert result["svc"] == "resolved-service"


def test_depends_multiple_params() -> None:
    """Multiple Depends() parameters are each resolved independently."""
    def get_db() -> str:
        return "db-connection"

    def get_cache() -> str:
        return "cache-connection"

    container = BrimleyContainer()
    _register_provider(container, "_t.inj_multi_db", "get_db", get_db, provider_name="get_db")
    _register_provider(container, "_t.inj_multi_cache", "get_cache", get_cache, provider_name="get_cache")
    context = BrimleyContext()
    context.container = container

    def handler(
        query: str,
        db: str = Depends(get_db),
        cache: str = Depends(get_cache),
    ) -> dict:
        return {"query": query, "db": db, "cache": cache}

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="multi_depends",
        type="python_function",
        return_shape="dict",
        handler="test.multi.handler",
    )
    result = dispatcher.run(func, {"query": "SELECT 1"}, context)

    assert result["query"] == "SELECT 1"
    assert result["db"] == "db-connection"
    assert result["cache"] == "cache-connection"


def test_depends_mixed_with_user_args_and_context() -> None:
    """Depends(), user args, and BrimleyContext injection coexist correctly."""
    def get_config_service() -> str:
        return "config-from-provider"

    container = BrimleyContainer()
    _register_provider(
        container, "_t.inj_mixed", "get_config_service", get_config_service,
        provider_name="get_config_service",
    )
    context = BrimleyContext()
    context.container = container

    def handler(
        user_input: str,
        ctx: BrimleyContext,
        cfg: str = Depends(get_config_service),
    ) -> dict:
        return {
            "user_input": user_input,
            "has_ctx": ctx is not None,
            "cfg": cfg,
        }

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="mixed_depends",
        type="python_function",
        return_shape="dict",
        handler="test.mixed.handler",
    )
    result = dispatcher.run(func, {"user_input": "hello"}, context)

    assert result["user_input"] == "hello"
    assert result["has_ctx"] is True
    assert result["cfg"] == "config-from-provider"


def test_depends_caller_supplied_takes_precedence() -> None:
    """Caller-supplied args override Depends() injection when both are present."""
    def get_service() -> str:
        return "injected-value"

    container = BrimleyContainer()
    _register_provider(container, "_t.inj_prec", "get_service", get_service, provider_name="get_service")
    context = BrimleyContext()
    context.container = container

    def handler(svc: str = Depends(get_service)) -> dict:
        return {"svc": svc}

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="precedence_depends",
        type="python_function",
        return_shape="dict",
        handler="test.prec.handler",
    )
    # Caller supplies "svc" explicitly — should take precedence over Depends()
    result = dispatcher.run(func, {"svc": "caller-override"}, context)

    assert result["svc"] == "caller-override"


def test_depends_missing_provider_raises_execution_error() -> None:
    """A Depends() referencing an unregistered provider raises BrimleyExecutionError."""
    def missing_provider() -> str:  # not registered
        return "never"

    container = BrimleyContainer()
    context = BrimleyContext()
    context.container = container

    def handler(svc: str = Depends(missing_provider)) -> dict:
        return {"svc": svc}

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="missing_depends",
        type="python_function",
        return_shape="dict",
        handler="test.missing.handler",
    )
    with pytest.raises(BrimleyExecutionError, match="missing_provider"):
        dispatcher.run(func, {}, context)


def test_depends_no_container_raises_execution_error() -> None:
    """A Depends() parameter raises BrimleyExecutionError when no container is configured."""
    def some_provider() -> str:
        return "value"

    context = BrimleyContext()
    assert context.container is None

    def handler(svc: str = Depends(some_provider)) -> dict:
        return {"svc": svc}

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="no_container_depends",
        type="python_function",
        return_shape="dict",
        handler="test.nocontainer.handler",
    )
    with pytest.raises(BrimleyExecutionError, match="no DI container"):
        dispatcher.run(func, {}, context)


def test_depends_resolved_via_request_scope() -> None:
    """A Depends() parameter resolves fresh instances from the request scope."""
    call_count = [0]

    def get_request_service() -> str:
        call_count[0] += 1
        return f"request-service-{call_count[0]}"

    container = BrimleyContainer()
    _register_provider(
        container, "_t.inj_scope", "get_request_service", get_request_service,
        scope="request", provider_name="get_request_service",
    )
    context = BrimleyContext()
    context.container = container

    def handler(svc: str = Depends(get_request_service)) -> dict:
        return {"svc": svc}

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="scope_depends",
        type="python_function",
        return_shape="dict",
        handler="test.scope.handler",
    )

    result1 = dispatcher.run(func, {}, context)
    result2 = dispatcher.run(func, {}, context)

    assert result1["svc"] == "request-service-1"
    assert result2["svc"] == "request-service-2"
    assert call_count[0] == 2, "Request-scoped provider must be called fresh each run"


def test_depends_string_provider_name() -> None:
    """Depends() can reference a provider by string name."""
    def get_named() -> str:
        return "named-provider-value"

    container = BrimleyContainer()
    _register_provider(
        container, "_t.inj_named", "get_named", get_named, provider_name="my_named_provider"
    )
    context = BrimleyContext()
    context.container = container

    def handler(svc: str = Depends("my_named_provider")) -> dict:
        return {"svc": svc}

    dispatcher = _DepsMockDispatcher(handler)
    func = PythonFunction(
        name="named_depends",
        type="python_function",
        return_shape="dict",
        handler="test.named.handler",
    )
    result = dispatcher.run(func, {}, context)

    assert result["svc"] == "named-provider-value"

