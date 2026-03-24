"""
Tests for B08-S7: Dispatcher request-scope lifecycle.

Verifies that every ``Dispatcher.run()`` invocation:
- enters a request scope when ``context.container`` is set
- tears the scope down in a ``finally`` block (even on exception)
- does not enter any scope when ``context.container`` is ``None``
"""

import sys
import types
from typing import Any, Iterator
from unittest.mock import patch

import pytest

from brimley.core.container import BrimleyContainer, _RequestScope
from brimley.core.context import BrimleyContext
from brimley.core.models import ProviderMetadata, PythonFunction
from brimley.execution.dispatcher import Dispatcher


# ---------------------------------------------------------------------------
# Helpers
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
    scope: str = "request",
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


def _make_python_func(handler_path: str = "test.module.func") -> PythonFunction:
    return PythonFunction(
        name="test_func",
        type="python_function",
        return_shape="dict",
        handler=handler_path,
    )


class _MockDispatcher(Dispatcher):
    """Dispatcher that replaces PythonRunner with a controllable stub."""

    def __init__(self, handler: Any) -> None:
        super().__init__()
        self._stub_handler = handler
        self.python_runner._load_handler = lambda _path, **_kw: self._stub_handler  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# B08-S7: request-scope entered and exited per run()
# ---------------------------------------------------------------------------


def test_request_scope_teardown_called_on_success() -> None:
    """_RequestScope._teardown() is called after a successful dispatch."""
    container = BrimleyContainer()
    context = BrimleyContext()
    context.container = container

    teardown_calls: list[bool] = []
    original_teardown = _RequestScope._teardown

    def tracking_teardown(self: _RequestScope) -> None:
        teardown_calls.append(True)
        original_teardown(self)

    def handler() -> dict:
        return {"ok": True}

    dispatcher = _MockDispatcher(handler)
    with patch.object(_RequestScope, "_teardown", tracking_teardown):
        result = dispatcher.run(_make_python_func(), {}, context)

    assert result == {"ok": True}
    assert teardown_calls == [True], "_teardown must be called once on success"


def test_request_scope_teardown_called_on_exception() -> None:
    """_RequestScope._teardown() is called even when the dispatch raises."""
    container = BrimleyContainer()
    context = BrimleyContext()
    context.container = container

    teardown_calls: list[bool] = []
    original_teardown = _RequestScope._teardown

    def tracking_teardown(self: _RequestScope) -> None:
        teardown_calls.append(True)
        original_teardown(self)

    def failing_handler() -> None:
        raise RuntimeError("intentional failure")

    dispatcher = _MockDispatcher(failing_handler)
    with patch.object(_RequestScope, "_teardown", tracking_teardown):
        with pytest.raises(RuntimeError, match="intentional failure"):
            dispatcher.run(_make_python_func(), {}, context)

    assert teardown_calls == [True], "_teardown must be called on exception"


def test_request_scope_provider_torn_down_after_resolution() -> None:
    """A request-scoped provider that was resolved is torn down at scope exit."""
    teardown_calls: list[str] = []

    def provider_factory() -> Iterator[str]:
        yield "service-value"
        teardown_calls.append("torn-down")

    container = BrimleyContainer()
    _register_provider(container, "_t.s7_success", "svc_factory", provider_factory, provider_name="svc")
    context = BrimleyContext()
    context.container = container

    # Resolve the provider inside the dispatch (via capturing_dispatch) so teardown runs
    original_dispatch = Dispatcher._dispatch_sync_call

    def resolving_dispatch(self, func, args, ctx, runtime_injections, request_ctx=None):
        if request_ctx is not None:
            request_ctx.resolve("svc")
        return original_dispatch(self, func, args, ctx, runtime_injections, request_ctx)

    def handler() -> dict:
        return {"ok": True}

    dispatcher = _MockDispatcher(handler)
    with patch.object(Dispatcher, "_dispatch_sync_call", resolving_dispatch):
        result = dispatcher.run(_make_python_func(), {}, context)

    assert result == {"ok": True}
    assert teardown_calls == ["torn-down"], "Request-scoped provider was not torn down"


def test_request_scope_provider_torn_down_on_exception() -> None:
    """Request-scoped provider teardown runs even when the dispatch raises."""
    teardown_calls: list[str] = []

    def provider_factory() -> Iterator[str]:
        yield "value"
        teardown_calls.append("torn-down-on-error")

    container = BrimleyContainer()
    _register_provider(container, "_t.s7_error", "svc_factory", provider_factory, provider_name="svc")
    context = BrimleyContext()
    context.container = container

    original_dispatch = Dispatcher._dispatch_sync_call

    def resolving_and_failing_dispatch(self, func, args, ctx, runtime_injections, request_ctx=None):
        if request_ctx is not None:
            request_ctx.resolve("svc")
        raise RuntimeError("intentional failure")

    dispatcher = _MockDispatcher(lambda: None)
    with patch.object(Dispatcher, "_dispatch_sync_call", resolving_and_failing_dispatch):
        with pytest.raises(RuntimeError, match="intentional failure"):
            dispatcher.run(_make_python_func(), {}, context)

    assert teardown_calls == ["torn-down-on-error"], "Teardown must run even on error"


def test_no_request_scope_when_container_is_none() -> None:
    """No request scope is entered when ``context.container`` is None."""
    context = BrimleyContext()
    assert context.container is None

    def handler() -> dict:
        return {"result": 42}

    dispatcher = _MockDispatcher(handler)
    result = dispatcher.run(_make_python_func(), {}, context)
    assert result == {"result": 42}


def test_fresh_scope_per_run_no_leaks() -> None:
    """Each Dispatcher.run() call gets its own request scope — no state leaks."""
    created_objects: list[object] = []

    def provider_factory() -> Iterator[object]:
        obj = object()
        created_objects.append(obj)  # hold a reference to prevent GC reuse
        yield obj

    container = BrimleyContainer()
    _register_provider(container, "_t.s7_leak", "svc_factory", provider_factory, provider_name="svc")
    context = BrimleyContext()
    context.container = container

    scope_refs: list[_RequestScope] = []

    original_dispatch = Dispatcher._dispatch_sync_call

    def capturing_dispatch(self, func, args, ctx, runtime_injections, request_ctx=None):
        if request_ctx is not None:
            scope_refs.append(request_ctx)
            request_ctx.resolve("svc")
        return original_dispatch(self, func, args, ctx, runtime_injections, request_ctx)

    def handler() -> dict:
        return {}

    dispatcher = _MockDispatcher(handler)
    with patch.object(Dispatcher, "_dispatch_sync_call", capturing_dispatch):
        dispatcher.run(_make_python_func(), {}, context)
        dispatcher.run(_make_python_func(), {}, context)

    assert len(scope_refs) == 2, "Expected two distinct request scopes"
    assert scope_refs[0] is not scope_refs[1], "Scopes must not be shared across calls"
    assert len(created_objects) == 2, "Two fresh provider instances should have been created"
    assert created_objects[0] is not created_objects[1], "Provider instances must differ across runs"


def test_request_scope_passed_to_dispatch_sync_call() -> None:
    """_dispatch_sync_call receives a non-None request_ctx when container is set."""
    container = BrimleyContainer()
    context = BrimleyContext()
    context.container = container

    received_ctx: list[Any] = []

    original_dispatch = Dispatcher._dispatch_sync_call

    def capturing_dispatch(self, func, args, ctx, runtime_injections, request_ctx=None):
        received_ctx.append(request_ctx)
        return original_dispatch(self, func, args, ctx, runtime_injections, request_ctx)

    def handler() -> dict:
        return {}

    dispatcher = _MockDispatcher(handler)
    with patch.object(Dispatcher, "_dispatch_sync_call", capturing_dispatch):
        dispatcher.run(_make_python_func(), {}, context)

    assert len(received_ctx) == 1
    assert isinstance(received_ctx[0], _RequestScope)


def test_request_scope_none_when_no_container() -> None:
    """_dispatch_sync_call receives request_ctx=None when container is None."""
    context = BrimleyContext()
    assert context.container is None

    received_ctx: list[Any] = []

    original_dispatch = Dispatcher._dispatch_sync_call

    def capturing_dispatch(self, func, args, ctx, runtime_injections, request_ctx=None):
        received_ctx.append(request_ctx)
        return original_dispatch(self, func, args, ctx, runtime_injections, request_ctx)

    def handler() -> dict:
        return {}

    dispatcher = _MockDispatcher(handler)
    with patch.object(Dispatcher, "_dispatch_sync_call", capturing_dispatch):
        dispatcher.run(_make_python_func(), {}, context)

    assert received_ctx == [None]


def test_fastmcp_path_teardown_called() -> None:
    """The FastMCP sync path also calls _RequestScope._teardown."""
    container = BrimleyContainer()
    context = BrimleyContext()
    context.container = container

    teardown_calls: list[bool] = []
    original_teardown = _RequestScope._teardown

    def tracking_teardown(self: _RequestScope) -> None:
        teardown_calls.append(True)
        original_teardown(self)

    FastMCPContext = type("Context", (), {"__module__": "mcp.server.fastmcp"})
    mock_mcp = FastMCPContext()

    def handler(mcp_ctx: FastMCPContext) -> dict:  # type: ignore[valid-type]
        return {"mcp": True}

    dispatcher = _MockDispatcher(handler)
    with patch.object(_RequestScope, "_teardown", tracking_teardown):
        result = dispatcher.run(
            _make_python_func(),
            {},
            context,
            runtime_injections={"mcp_context": mock_mcp},
        )

    assert result == {"mcp": True}
    assert teardown_calls == [True], "_teardown must be called on FastMCP path"


