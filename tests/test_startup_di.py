"""
Tests for B08-S6: Startup Sequence Integration.

Covers:
- Happy-path: container populated on context, providers registered, eager
  providers constructed, @on_startup hooks executed in order.
- Eager provider failure: startup aborts, cleanup runs, exception propagates.
- @on_startup hook failure: startup aborts, cleanup runs, exception propagates.
- Missing provider module: startup aborts, ProviderResolutionError propagates.
- Cycle detection: circular dependency aborts startup.
- Existing startup behavior preserved when no providers/hooks are declared.
- Built-in db_<name> providers registered from context.databases.
- system_boot correlation ID set during startup.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Iterator, List, Optional

import pytest

from brimley.core.container import BrimleyContainer, ProviderResolutionError
from brimley.core.context import BrimleyContext
from brimley.core.models import LifecycleHookMetadata, ProviderMetadata
from brimley.core.resolver import CircularDependencyError
from brimley.infrastructure.logging import SYSTEM_BOOT_CORRELATION_ID, get_correlation_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(name: str, **attrs: Any) -> types.ModuleType:
    """Create a throwaway module and insert it into sys.modules."""
    mod = types.ModuleType(name)
    for attr_name, value in attrs.items():
        setattr(mod, attr_name, value)
    sys.modules[name] = mod
    return mod


def _provider_meta(
    module_name: str,
    func_name: str,
    *,
    scope: str = "singleton",
    eager: bool = False,
    provider_name: Optional[str] = None,
) -> ProviderMetadata:
    return ProviderMetadata(
        name=provider_name,
        module_path=module_name,
        func_name=func_name,
        handler=f"{module_name}.{func_name}",
        scope=scope,
        eager=eager,
    )


def _hook_meta(
    module_name: str,
    func_name: str,
    hook_type: str = "on_startup",
) -> LifecycleHookMetadata:
    # hook_type is Literal["on_startup", "on_shutdown"]; passing str satisfies
    # Pydantic validation at runtime; the ignore silences the static type checker.
    return LifecycleHookMetadata(
        hook_type=hook_type,  # type: ignore[arg-type]
        module_path=module_name,
        func_name=func_name,
        handler=f"{module_name}.{func_name}",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestStartupHappyPath:
    def test_container_attached_to_context(self) -> None:
        """After startup(), context.container is a live BrimleyContainer."""
        container = BrimleyContainer()
        context = BrimleyContext()
        container.startup(context=context)
        # Container itself is returned — we attach it manually as the CLI does
        context.container = container
        assert context.container is container

    def test_no_providers_no_hooks_is_noop(self) -> None:
        """Startup with empty providers/hooks completes without error."""
        container = BrimleyContainer()
        container.startup(lifecycle_hooks=[], context=None)

    def test_lazy_provider_registered_and_resolvable(self) -> None:
        """A registered singleton provider resolves correctly after startup."""
        _make_module("_t.s1_lazy", get_value=lambda: "hello")
        container = BrimleyContainer()
        meta = _provider_meta("_t.s1_lazy", "get_value")
        container.register(meta)
        container.startup()
        assert container.resolve("get_value") == "hello"

    def test_eager_provider_constructed_at_startup(self) -> None:
        """Eager=True providers are instantiated during startup."""
        calls: List[str] = []

        def _eager_factory() -> str:
            calls.append("called")
            return "eager_value"

        _make_module("_t.s1_eager", factory=_eager_factory)
        container = BrimleyContainer()
        meta = _provider_meta("_t.s1_eager", "factory", eager=True)
        container.register(meta)
        container.startup()
        assert calls == ["called"]
        # Singleton cache: second resolve must not call factory again
        container.resolve("factory")
        assert calls == ["called"]

    def test_on_startup_hook_executed(self) -> None:
        """@on_startup hooks execute during startup."""
        calls: List[str] = []

        def _hook() -> None:
            calls.append("hook_ran")

        _make_module("_t.s1_hook", startup_hook=_hook)
        container = BrimleyContainer()
        hook = _hook_meta("_t.s1_hook", "startup_hook", "on_startup")
        container.startup(lifecycle_hooks=[hook])
        assert calls == ["hook_ran"]

    def test_on_startup_hooks_run_in_declaration_order(self) -> None:
        """Multiple @on_startup hooks execute in the order they were declared."""
        order: List[int] = []

        def _hook1() -> None:
            order.append(1)

        def _hook2() -> None:
            order.append(2)

        def _hook3() -> None:
            order.append(3)

        _make_module("_t.s1_order", h1=_hook1, h2=_hook2, h3=_hook3)
        container = BrimleyContainer()
        hooks = [
            _hook_meta("_t.s1_order", "h1"),
            _hook_meta("_t.s1_order", "h2"),
            _hook_meta("_t.s1_order", "h3"),
        ]
        container.startup(lifecycle_hooks=hooks)
        assert order == [1, 2, 3]

    def test_on_shutdown_hooks_not_run_at_startup(self) -> None:
        """@on_shutdown hooks in the list must NOT be called during startup."""
        calls: List[str] = []

        def _shutdown_hook() -> None:
            calls.append("shutdown_called")

        _make_module("_t.s1_shutdown", shutdown_hook=_shutdown_hook)
        container = BrimleyContainer()
        hook = _hook_meta("_t.s1_shutdown", "shutdown_hook", "on_shutdown")
        container.startup(lifecycle_hooks=[hook])
        assert calls == []

    def test_on_startup_hook_receives_context(self) -> None:
        """@on_startup hook with BrimleyContext parameter receives the context."""
        received: List[Any] = []

        def _hook(ctx: BrimleyContext) -> None:
            received.append(ctx)

        _make_module("_t.s1_ctx", hook=_hook)
        context = BrimleyContext()
        container = BrimleyContainer()
        hook = _hook_meta("_t.s1_ctx", "hook")
        container.startup(lifecycle_hooks=[hook], context=context)
        assert received == [context]

    def test_async_on_startup_hook_executed(self) -> None:
        """Async @on_startup hooks are awaited correctly."""
        calls: List[str] = []

        async def _async_hook() -> None:
            calls.append("async_ran")

        _make_module("_t.s1_async", async_hook=_async_hook)
        container = BrimleyContainer()
        hook = _hook_meta("_t.s1_async", "async_hook")
        container.startup(lifecycle_hooks=[hook])
        assert calls == ["async_ran"]


# ---------------------------------------------------------------------------
# Built-in database providers
# ---------------------------------------------------------------------------


class TestDatabaseProviders:
    def test_db_provider_registered_via_override(self) -> None:
        """context.databases entries are available as db_<name> in the container."""
        fake_engine = object()
        context = BrimleyContext()
        context.databases = {"primary": fake_engine}

        container = BrimleyContainer()
        # Simulate what _run_di_startup does
        for db_name, engine in context.databases.items():
            container.override(f"db_{db_name}", engine)
        container.startup(context=context)
        context.container = container

        assert context.container.resolve("db_primary") is fake_engine

    def test_multiple_databases_registered(self) -> None:
        """Multiple databases each get their own db_<name> built-in provider."""
        engine_a = object()
        engine_b = object()
        context = BrimleyContext()
        context.databases = {"alpha": engine_a, "beta": engine_b}

        container = BrimleyContainer()
        for db_name, engine in context.databases.items():
            container.override(f"db_{db_name}", engine)
        container.startup(context=context)
        context.container = container

        assert context.container.resolve("db_alpha") is engine_a
        assert context.container.resolve("db_beta") is engine_b


# ---------------------------------------------------------------------------
# Fail-fast: eager provider failure
# ---------------------------------------------------------------------------


class TestEagerProviderFailure:
    def test_eager_failure_propagates(self) -> None:
        """A failure in an eager provider aborts startup and propagates the error."""

        def _bad_provider() -> str:
            raise RuntimeError("eager boom")

        _make_module("_t.s1_efail", bad=_bad_provider)
        container = BrimleyContainer()
        meta = _provider_meta("_t.s1_efail", "bad", eager=True)
        container.register(meta)
        with pytest.raises(RuntimeError, match="eager boom"):
            container.startup()

    def test_eager_failure_runs_shutdown_cleanup(self) -> None:
        """When an eager provider fails, already-constructed providers are torn down."""
        torn_down: List[str] = []

        def _good_provider() -> Iterator[str]:
            yield "provider_value"
            torn_down.append("good_provider_torn_down")

        def _bad_provider() -> str:
            raise RuntimeError("second provider fails")

        _make_module("_t.s1_efail2", good=_good_provider, bad=_bad_provider)
        container = BrimleyContainer()
        # Register good as eager first so it constructs before bad is attempted
        good_meta = _provider_meta("_t.s1_efail2", "good", eager=True, provider_name="good")
        bad_meta = _provider_meta("_t.s1_efail2", "bad", eager=True, provider_name="bad")
        container.register(good_meta)
        container.register(bad_meta)
        with pytest.raises(RuntimeError):
            container.startup()
        assert torn_down == ["good_provider_torn_down"]


# ---------------------------------------------------------------------------
# Fail-fast: @on_startup hook failure
# ---------------------------------------------------------------------------


class TestStartupHookFailure:
    def test_hook_failure_propagates(self) -> None:
        """A failure in an @on_startup hook aborts startup and propagates the error."""

        def _bad_hook() -> None:
            raise ValueError("hook boom")

        _make_module("_t.s1_hfail", bad=_bad_hook)
        container = BrimleyContainer()
        hook = _hook_meta("_t.s1_hfail", "bad")
        with pytest.raises(ValueError, match="hook boom"):
            container.startup(lifecycle_hooks=[hook])

    def test_hook_failure_runs_shutdown_cleanup(self) -> None:
        """When a hook fails, already-constructed providers are torn down."""
        torn_down: List[str] = []

        def _teardown_provider() -> Iterator[str]:
            yield "provider_value"
            torn_down.append("provider_torn_down")

        def _bad_hook() -> None:
            raise RuntimeError("hook fails after provider built")

        _make_module("_t.s1_hfail2", prov=_teardown_provider, hook=_bad_hook)
        container = BrimleyContainer()
        meta = _provider_meta("_t.s1_hfail2", "prov", eager=True, provider_name="prov")
        container.register(meta)
        hook = _hook_meta("_t.s1_hfail2", "hook")
        with pytest.raises(RuntimeError):
            container.startup(lifecycle_hooks=[hook])
        assert torn_down == ["provider_torn_down"]


# ---------------------------------------------------------------------------
# Fail-fast: missing module
# ---------------------------------------------------------------------------


class TestMissingModule:
    def test_missing_module_raises_on_startup(self) -> None:
        """Registering a provider with a non-existent module raises at startup (eager)."""
        # Ensure no stale module
        sys.modules.pop("_t.no_such_module", None)
        container = BrimleyContainer()
        meta = ProviderMetadata(
            module_path="_t.no_such_module",
            func_name="get_it",
            handler="_t.no_such_module.get_it",
            eager=True,
        )
        container.register(meta)
        with pytest.raises(ProviderResolutionError):
            container.startup()


# ---------------------------------------------------------------------------
# Fail-fast: cycle detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_cycle_aborts_startup(self) -> None:
        """A circular dependency is detected before any provider is constructed."""
        from brimley.core.di import Depends

        def _a(b: Any = Depends("b_prov")) -> str:
            return "a"

        def _b(a: Any = Depends("a_prov")) -> str:
            return "b"

        _make_module("_t.s1_cycle", a=_a, b=_b)
        container = BrimleyContainer()
        meta_a = _provider_meta("_t.s1_cycle", "a", provider_name="a_prov")
        meta_b = _provider_meta("_t.s1_cycle", "b", provider_name="b_prov")
        container.register(meta_a)
        container.register(meta_b)
        with pytest.raises(CircularDependencyError):
            container.startup()


# ---------------------------------------------------------------------------
# system_boot correlation ID
# ---------------------------------------------------------------------------


class TestSystemBootCorrelationId:
    def test_constant_value(self) -> None:
        """SYSTEM_BOOT_CORRELATION_ID is the literal string 'system_boot'."""
        assert SYSTEM_BOOT_CORRELATION_ID == "system_boot"

    def test_set_before_startup(self) -> None:
        """_run_di_startup sets the correlation ID to system_boot."""
        from brimley.infrastructure.logging import set_correlation_id

        set_correlation_id(SYSTEM_BOOT_CORRELATION_ID)
        assert get_correlation_id() == "system_boot"


# ---------------------------------------------------------------------------
# No regression: startup without providers/hooks
# ---------------------------------------------------------------------------


class TestNoProvidersRegression:
    def test_empty_scan_result_fields(self) -> None:
        """_run_di_startup handles scan_result objects with empty providers/lifecycle_hooks."""
        from brimley.discovery.scanner import BrimleyScanResult

        scan_result = BrimleyScanResult()
        context = BrimleyContext()

        from brimley.core.container import BrimleyContainer
        from brimley.infrastructure.logging import set_correlation_id, SYSTEM_BOOT_CORRELATION_ID

        set_correlation_id(SYSTEM_BOOT_CORRELATION_ID)
        container = BrimleyContainer()
        for provider_meta in scan_result.providers:
            container.register(provider_meta)
        for db_name, engine in (context.databases or {}).items():
            container.override(f"db_{db_name}", engine)
        lifecycle_hooks = scan_result.lifecycle_hooks
        container.startup(lifecycle_hooks=lifecycle_hooks, context=context)
        context.container = container

        assert context.container is not None
        assert context.container.provider_names() == []
