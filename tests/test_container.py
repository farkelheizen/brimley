"""
Tests for BrimleyContainer (B08-S4).

Covers:
- Provider registration and duplicate detection
- Singleton resolution (lazy and eager)
- Yield-based teardown
- Override and reset_overrides
- Shutdown lifecycle
- Request scope (context manager, request-scoped providers, teardown)
- Thread-safe singleton resolution
- BrimleyContext injection into providers
- Async provider support (coroutines and async generators)
"""

from __future__ import annotations

import sys
import threading
import types
from typing import Any, Iterator, Optional

import pytest

from brimley.core.container import (
    BrimleyContainer,
    DuplicateProviderError,
    ProviderResolutionError,
    _RequestScope,
)
from brimley.core.models import ProviderMetadata


# ---------------------------------------------------------------------------
# Helpers: register callables without a real module on disk
# ---------------------------------------------------------------------------


def _make_module(name: str, **attrs: Any) -> types.ModuleType:
    """Create a throwaway module and insert it into sys.modules."""
    mod = types.ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(mod, attr_name, value)
    sys.modules[name] = mod
    return mod


def _register(
    container: BrimleyContainer,
    module_name: str,
    func_name: str,
    fn: Any,
    scope: str = "singleton",
    eager: bool = False,
    provider_name: Optional[str] = None,
) -> ProviderMetadata:
    """Helper: create a fake module, add *fn*, and register it."""
    _make_module(module_name, **{func_name: fn})
    meta = ProviderMetadata(
        name=provider_name,
        module_path=module_name,
        func_name=func_name,
        handler=f"{module_name}.{func_name}",
        scope=scope,
        eager=eager,
    )
    container.register(meta)
    return meta


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_adds_provider(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.reg1", "get_db", lambda: "db")
        assert container.has_provider("get_db")

    def test_register_uses_func_name_as_default_name(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.reg2", "my_service", lambda: "svc")
        assert container.has_provider("my_service")

    def test_register_uses_explicit_name(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.reg3", "my_service", lambda: "svc", provider_name="database")
        assert container.has_provider("database")
        assert not container.has_provider("my_service")

    def test_duplicate_registration_raises(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.dup1", "get_db", lambda: "a")
        with pytest.raises(DuplicateProviderError, match="'get_db'"):
            _register(container, "_t.dup2", "get_db", lambda: "b")

    def test_provider_names_returns_all(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.names1", "svc_a", lambda: "a")
        _register(container, "_t.names2", "svc_b", lambda: "b")
        assert set(container.provider_names()) == {"svc_a", "svc_b"}

    def test_has_provider_false_for_unknown(self) -> None:
        container = BrimleyContainer()
        assert not container.has_provider("nonexistent")


# ---------------------------------------------------------------------------
# Singleton resolution
# ---------------------------------------------------------------------------


class TestSingletonResolution:
    def test_resolve_returns_value(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.sr1", "get_val", lambda: 42)
        assert container.resolve("get_val") == 42

    def test_singleton_cached_on_second_resolve(self) -> None:
        container = BrimleyContainer()
        call_count = [0]

        def factory() -> dict:
            call_count[0] += 1
            return {"x": call_count[0]}

        _register(container, "_t.sr2", "factory", factory)
        first = container.resolve("factory")
        second = container.resolve("factory")
        assert first is second
        assert call_count[0] == 1

    def test_resolve_unknown_raises(self) -> None:
        container = BrimleyContainer()
        with pytest.raises(ProviderResolutionError, match="'missing_provider'"):
            container.resolve("missing_provider")

    def test_invalid_handler_path_raises(self) -> None:
        container = BrimleyContainer()
        meta = ProviderMetadata(
            module_path="some_module",
            func_name="func",
            handler="no_dot_here",
            scope="singleton",
        )
        # Bypass the duplicate check by registering directly
        container._registry["bad_path"] = meta
        container._provider_locks["bad_path"] = threading.Lock()
        with pytest.raises(ProviderResolutionError, match="Invalid handler path"):
            container.resolve("bad_path")

    def test_resolve_missing_module_raises(self) -> None:
        container = BrimleyContainer()
        meta = ProviderMetadata(
            module_path="does_not_exist_anywhere",
            func_name="func",
            handler="does_not_exist_anywhere.func",
            scope="singleton",
        )
        container._registry["bad_mod"] = meta
        container._provider_locks["bad_mod"] = threading.Lock()
        with pytest.raises(ProviderResolutionError, match="Cannot import module"):
            container.resolve("bad_mod")


# ---------------------------------------------------------------------------
# Eager initialization
# ---------------------------------------------------------------------------


class TestEagerInitialization:
    def test_eager_singleton_resolved_at_init_eager(self) -> None:
        container = BrimleyContainer()
        resolved = []

        def factory() -> str:
            resolved.append("called")
            return "value"

        _register(container, "_t.eager1", "factory", factory, eager=True)
        assert resolved == []
        container.init_eager()
        assert resolved == ["called"]

    def test_non_eager_singleton_not_resolved_at_init_eager(self) -> None:
        container = BrimleyContainer()
        resolved = []

        def factory() -> str:
            resolved.append("called")
            return "value"

        _register(container, "_t.eager2", "lazy_factory", factory, eager=False)
        container.init_eager()
        assert resolved == []

    def test_request_scoped_not_resolved_at_init_eager(self) -> None:
        container = BrimleyContainer()
        resolved = []

        def factory() -> str:
            resolved.append("called")
            return "value"

        _register(container, "_t.eager3", "req_factory", factory, scope="request", eager=True)
        container.init_eager()
        assert resolved == []


# ---------------------------------------------------------------------------
# Yield-based teardown
# ---------------------------------------------------------------------------


class TestYieldTeardown:
    def test_generator_value_returned(self) -> None:
        container = BrimleyContainer()
        teardown_called = []

        def factory() -> Iterator[str]:
            yield "resource"
            teardown_called.append("torn_down")

        _register(container, "_t.ytd1", "factory", factory)
        value = container.resolve("factory")
        assert value == "resource"
        assert teardown_called == []

    def test_shutdown_runs_generator_teardown(self) -> None:
        container = BrimleyContainer()
        teardown_log: list = []

        def factory() -> Iterator[str]:
            yield "resource"
            teardown_log.append("done")

        _register(container, "_t.ytd2", "factory", factory)
        container.resolve("factory")
        assert teardown_log == []
        container.shutdown()
        assert teardown_log == ["done"]

    def test_shutdown_clears_singletons(self) -> None:
        container = BrimleyContainer()
        call_count = [0]

        def factory() -> Iterator[int]:
            call_count[0] += 1
            yield call_count[0]

        _register(container, "_t.ytd3", "factory", factory)
        v1 = container.resolve("factory")
        assert v1 == 1
        container.shutdown()
        # After shutdown _singletons is cleared; next resolve re-calls the factory
        v2 = container.resolve("factory")
        assert v2 == 2
        assert call_count[0] == 2

    def test_teardown_order_reversed(self) -> None:
        container = BrimleyContainer()
        log: list = []

        def factory_a() -> Iterator[str]:
            yield "a"
            log.append("teardown_a")

        def factory_b() -> Iterator[str]:
            yield "b"
            log.append("teardown_b")

        _register(container, "_t.order1", "svc_a", factory_a)
        _register(container, "_t.order2", "svc_b", factory_b)
        container.resolve("svc_a")
        container.resolve("svc_b")
        container.shutdown()
        # Teardown should be in reverse init order
        assert log == ["teardown_b", "teardown_a"]


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


class TestOverrides:
    def test_override_replaces_provider(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.ov1", "get_db", lambda: "real_db")
        container.override("get_db", "mock_db")
        assert container.resolve("get_db") == "mock_db"

    def test_override_works_without_registration(self) -> None:
        container = BrimleyContainer()
        container.override("anything", "mock_value")
        assert container.resolve("anything") == "mock_value"

    def test_reset_overrides_restores_original(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.ov2", "get_val", lambda: "real")
        container.override("get_val", "mock")
        container.reset_overrides()
        assert container.resolve("get_val") == "real"

    def test_reset_overrides_clears_all(self) -> None:
        container = BrimleyContainer()
        container.override("a", 1)
        container.override("b", 2)
        container.reset_overrides()
        with pytest.raises(ProviderResolutionError):
            container.resolve("a")


# ---------------------------------------------------------------------------
# Request scope
# ---------------------------------------------------------------------------


class TestRequestScope:
    def test_request_scope_returns_scope_object(self) -> None:
        container = BrimleyContainer()
        with container.request_scope() as scope:
            assert isinstance(scope, _RequestScope)

    def test_request_scope_resolves_request_scoped_provider(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.rs1", "req_svc", lambda: "req_value", scope="request")
        with container.request_scope() as scope:
            value = scope.resolve("req_svc")
        assert value == "req_value"

    def test_request_scope_caches_within_scope(self) -> None:
        container = BrimleyContainer()
        call_count = [0]

        def factory() -> dict:
            call_count[0] += 1
            return {"n": call_count[0]}

        _register(container, "_t.rs2", "req_svc", factory, scope="request")
        with container.request_scope() as scope:
            first = scope.resolve("req_svc")
            second = scope.resolve("req_svc")
        assert first is second
        assert call_count[0] == 1

    def test_request_scope_fresh_per_scope(self) -> None:
        container = BrimleyContainer()
        call_count = [0]

        def factory() -> dict:
            call_count[0] += 1
            return {"n": call_count[0]}

        _register(container, "_t.rs3", "req_svc", factory, scope="request")
        with container.request_scope() as scope1:
            v1 = scope1.resolve("req_svc")
        with container.request_scope() as scope2:
            v2 = scope2.resolve("req_svc")
        assert v1 is not v2
        assert call_count[0] == 2

    def test_request_scope_teardown_on_exit(self) -> None:
        container = BrimleyContainer()
        teardown_log: list = []

        def factory() -> Iterator[str]:
            yield "resource"
            teardown_log.append("torn_down")

        _register(container, "_t.rs4", "req_svc", factory, scope="request")
        with container.request_scope() as scope:
            scope.resolve("req_svc")
        assert teardown_log == ["torn_down"]

    def test_request_scope_teardown_on_exception(self) -> None:
        container = BrimleyContainer()
        teardown_log: list = []

        def factory() -> Iterator[str]:
            yield "resource"
            teardown_log.append("torn_down")

        _register(container, "_t.rs5", "req_svc", factory, scope="request")
        with pytest.raises(RuntimeError):
            with container.request_scope() as scope:
                scope.resolve("req_svc")
                raise RuntimeError("oops")
        assert teardown_log == ["torn_down"]

    def test_request_scope_singleton_delegates_to_container(self) -> None:
        container = BrimleyContainer()
        call_count = [0]

        def factory() -> str:
            call_count[0] += 1
            return "singleton_value"

        _register(container, "_t.rs6", "singleton_svc", factory, scope="singleton")
        with container.request_scope() as scope:
            v1 = scope.resolve("singleton_svc")
            v2 = scope.resolve("singleton_svc")
        assert v1 == "singleton_value"
        assert call_count[0] == 1

    def test_request_scope_override_respected(self) -> None:
        container = BrimleyContainer()
        _register(container, "_t.rs7", "req_svc", lambda: "real", scope="request")
        container.override("req_svc", "mock")
        with container.request_scope() as scope:
            assert scope.resolve("req_svc") == "mock"

    def test_request_scope_unknown_provider_raises(self) -> None:
        container = BrimleyContainer()
        with container.request_scope() as scope:
            with pytest.raises(ProviderResolutionError, match="'unknown'"):
                scope.resolve("unknown")


# ---------------------------------------------------------------------------
# BrimleyContext injection
# ---------------------------------------------------------------------------


class TestContextInjection:
    def test_context_injected_when_annotated(self) -> None:
        from brimley.core.context import BrimleyContext

        received: list = []

        def factory(ctx: BrimleyContext) -> str:
            received.append(ctx)
            return "ok"

        container = BrimleyContainer()
        _register(container, "_t.ctx1", "factory", factory)
        ctx = BrimleyContext()
        result = container.resolve("factory", context=ctx)
        assert result == "ok"
        assert received[0] is ctx

    def test_context_not_injected_when_not_annotated(self) -> None:
        """Provider with no BrimleyContext annotation should work without context."""

        def factory() -> str:
            return "no_context"

        container = BrimleyContainer()
        _register(container, "_t.ctx2", "factory", factory)
        assert container.resolve("factory") == "no_context"

    def test_context_skipped_when_context_is_none(self) -> None:
        """Provider without required BrimleyContext param works when context=None."""

        def factory() -> str:
            return "no_context_needed"

        container = BrimleyContainer()
        _register(container, "_t.ctx3", "factory", factory)
        # Context=None is fine as long as the provider doesn't require it
        result = container.resolve("factory", context=None)
        assert result == "no_context_needed"


# ---------------------------------------------------------------------------
# Depends injection (provider-to-provider)
# ---------------------------------------------------------------------------


class TestDependsInjection:
    def test_depends_resolved_transitively(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_t.dep1", "get_conn", lambda: "connection")

        def get_service(conn=Depends("get_conn")) -> str:
            return f"service({conn})"

        _register(container, "_t.dep2", "get_service", get_service)
        result = container.resolve("get_service")
        assert result == "service(connection)"

    def test_depends_resolved_in_request_scope(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_t.dep3", "get_val", lambda: "val", scope="singleton")

        def get_service(v=Depends("get_val")) -> str:
            return f"svc({v})"

        _register(container, "_t.dep4", "get_service", get_service, scope="request")
        with container.request_scope() as scope:
            result = scope.resolve("get_service")
        assert result == "svc(val)"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_singleton_only_initialized_once_concurrently(self) -> None:
        container = BrimleyContainer()
        call_count = [0]
        start_event = threading.Event()

        def factory() -> dict:
            call_count[0] += 1
            return {"n": call_count[0]}

        _register(container, "_t.ts1", "factory", factory)

        results: list = []

        def resolve() -> None:
            start_event.wait()
            results.append(container.resolve("factory"))

        threads = [threading.Thread(target=resolve) for _ in range(10)]
        for t in threads:
            t.start()
        start_event.set()
        for t in threads:
            t.join()

        assert call_count[0] == 1
        assert all(r is results[0] for r in results)


# ---------------------------------------------------------------------------
# Async provider support
# ---------------------------------------------------------------------------


class TestAsyncProviders:
    def test_async_function_provider(self) -> None:
        import asyncio

        container = BrimleyContainer()

        async def async_factory() -> str:
            await asyncio.sleep(0)
            return "async_value"

        _register(container, "_t.async1", "async_factory", async_factory)
        result = container.resolve("async_factory")
        assert result == "async_value"

    def test_async_generator_provider(self) -> None:
        import asyncio

        container = BrimleyContainer()
        teardown_log: list = []

        async def async_factory():
            await asyncio.sleep(0)
            yield "async_resource"
            teardown_log.append("async_torn_down")

        _register(container, "_t.async2", "async_factory", async_factory)
        result = container.resolve("async_factory")
        assert result == "async_resource"
        container.shutdown()
        assert teardown_log == ["async_torn_down"]
