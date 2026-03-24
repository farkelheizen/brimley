"""
Tests for DependencyResolver (B08-S5).

Covers:
- topological_sort: simple dependencies, transitive, multiple roots
- detect_cycles: direct cycles, indirect cycles
- get_dependencies: Depends detection, BrimleyContext exclusion
- Error propagation: missing providers referenced as dependencies
"""

from __future__ import annotations

import sys
import types
from typing import Any, Optional

import pytest

from brimley.core.container import BrimleyContainer, ProviderResolutionError
from brimley.core.models import ProviderMetadata
from brimley.core.resolver import CircularDependencyError, DependencyResolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(name: str, **attrs: Any) -> types.ModuleType:
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
    provider_name: Optional[str] = None,
) -> ProviderMetadata:
    _make_module(module_name, **{func_name: fn})
    meta = ProviderMetadata(
        name=provider_name,
        module_path=module_name,
        func_name=func_name,
        handler=f"{module_name}.{func_name}",
        scope=scope,
    )
    container.register(meta)
    return meta


# ---------------------------------------------------------------------------
# topological_sort
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def test_single_provider_no_deps(self) -> None:
        container = BrimleyContainer()
        _register(container, "_r.ts1", "svc_a", lambda: "a")
        resolver = DependencyResolver(container)
        order = resolver.topological_sort(["svc_a"])
        assert order == ["svc_a"]

    def test_dependency_before_dependant(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_r.ts2", "get_conn", lambda: "conn")

        def get_service(conn=Depends("get_conn")) -> str:
            return "svc"

        _register(container, "_r.ts3", "get_service", get_service)
        resolver = DependencyResolver(container)
        order = resolver.topological_sort(["get_service", "get_conn"])
        assert order.index("get_conn") < order.index("get_service")

    def test_transitive_dependency_order(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_r.ts4", "layer_c", lambda: "c")

        def layer_b(c=Depends("layer_c")) -> str:
            return "b"

        _register(container, "_r.ts5", "layer_b", layer_b)

        def layer_a(b=Depends("layer_b")) -> str:
            return "a"

        _register(container, "_r.ts6", "layer_a", layer_a)
        resolver = DependencyResolver(container)
        order = resolver.topological_sort(["layer_a"])
        assert order.index("layer_c") < order.index("layer_b")
        assert order.index("layer_b") < order.index("layer_a")

    def test_multiple_independent_providers(self) -> None:
        container = BrimleyContainer()
        _register(container, "_r.ts7", "svc_x", lambda: "x")
        _register(container, "_r.ts8", "svc_y", lambda: "y")
        resolver = DependencyResolver(container)
        order = resolver.topological_sort(["svc_x", "svc_y"])
        assert set(order) == {"svc_x", "svc_y"}

    def test_sort_all_providers_when_names_none(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_r.ts9", "base", lambda: "base")

        def dependent(b=Depends("base")) -> str:
            return "dep"

        _register(container, "_r.ts10", "dependent", dependent)
        resolver = DependencyResolver(container)
        order = resolver.topological_sort()
        assert "base" in order
        assert "dependent" in order
        assert order.index("base") < order.index("dependent")

    def test_diamond_dependency(self) -> None:
        """A -> B, A -> C, B -> D, C -> D should not duplicate D."""
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_r.dia1", "svc_d", lambda: "d")

        def svc_b(d=Depends("svc_d")) -> str:
            return "b"

        def svc_c(d=Depends("svc_d")) -> str:
            return "c"

        def svc_a(b=Depends("svc_b"), c=Depends("svc_c")) -> str:
            return "a"

        _register(container, "_r.dia2", "svc_b", svc_b)
        _register(container, "_r.dia3", "svc_c", svc_c)
        _register(container, "_r.dia4", "svc_a", svc_a)

        resolver = DependencyResolver(container)
        order = resolver.topological_sort(["svc_a"])
        # No duplicates
        assert len(order) == len(set(order))
        # All present
        assert set(order) == {"svc_d", "svc_b", "svc_c", "svc_a"}
        # D before both B and C; B and C before A
        assert order.index("svc_d") < order.index("svc_b")
        assert order.index("svc_d") < order.index("svc_c")
        assert order.index("svc_b") < order.index("svc_a")
        assert order.index("svc_c") < order.index("svc_a")


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_direct_cycle_raises(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()

        def alpha(b=Depends("beta")) -> str:
            return "a"

        def beta(a=Depends("alpha")) -> str:
            return "b"

        _register(container, "_r.cyc1", "alpha", alpha)
        _register(container, "_r.cyc2", "beta", beta)

        resolver = DependencyResolver(container)
        with pytest.raises(CircularDependencyError, match="Circular dependency"):
            resolver.topological_sort(["alpha"])

    def test_indirect_cycle_raises(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()

        def svc_a(b=Depends("svc_b")) -> str:
            return "a"

        def svc_b(c=Depends("svc_c")) -> str:
            return "b"

        def svc_c(a=Depends("svc_a")) -> str:
            return "c"

        _register(container, "_r.cyc3", "svc_a", svc_a)
        _register(container, "_r.cyc4", "svc_b", svc_b)
        _register(container, "_r.cyc5", "svc_c", svc_c)

        resolver = DependencyResolver(container)
        with pytest.raises(CircularDependencyError):
            resolver.topological_sort(["svc_a"])

    def test_detect_cycles_convenience(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()

        def p(q=Depends("q")) -> str:
            return "p"

        def q(p=Depends("p")) -> str:
            return "q"

        _register(container, "_r.cyc6", "p", p)
        _register(container, "_r.cyc7", "q", q)

        resolver = DependencyResolver(container)
        with pytest.raises(CircularDependencyError):
            resolver.detect_cycles()

    def test_no_cycle_does_not_raise(self) -> None:
        container = BrimleyContainer()
        _register(container, "_r.nc1", "svc_x", lambda: "x")
        _register(container, "_r.nc2", "svc_y", lambda: "y")
        resolver = DependencyResolver(container)
        resolver.detect_cycles()  # should not raise


# ---------------------------------------------------------------------------
# get_dependencies
# ---------------------------------------------------------------------------


class TestGetDependencies:
    def test_no_deps_returns_empty(self) -> None:
        container = BrimleyContainer()
        _register(container, "_r.gd1", "standalone", lambda: "v")
        resolver = DependencyResolver(container)
        assert resolver.get_dependencies("standalone") == []

    def test_depends_returns_dep_name(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_r.gd2", "base", lambda: "b")

        def svc(b=Depends("base")) -> str:
            return "s"

        _register(container, "_r.gd3", "svc", svc)
        resolver = DependencyResolver(container)
        assert resolver.get_dependencies("svc") == ["base"]

    def test_brimley_context_excluded_from_deps(self) -> None:
        from brimley.core.context import BrimleyContext
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_r.gd4", "base", lambda: "b")

        def svc(ctx: BrimleyContext, b=Depends("base")) -> str:
            return "s"

        _register(container, "_r.gd5", "svc", svc)
        resolver = DependencyResolver(container)
        deps = resolver.get_dependencies("svc")
        # Only the Depends() dep should appear; BrimleyContext is injected, not a dep
        assert deps == ["base"]

    def test_unknown_provider_returns_empty(self) -> None:
        container = BrimleyContainer()
        resolver = DependencyResolver(container)
        # Unregistered providers return empty deps (graceful)
        assert resolver.get_dependencies("does_not_exist") == []

    def test_multiple_depends_returned(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()
        _register(container, "_r.gd6", "dep_x", lambda: "x")
        _register(container, "_r.gd7", "dep_y", lambda: "y")

        def svc(x=Depends("dep_x"), y=Depends("dep_y")) -> str:
            return "s"

        _register(container, "_r.gd8", "svc", svc)
        resolver = DependencyResolver(container)
        deps = resolver.get_dependencies("svc")
        assert set(deps) == {"dep_x", "dep_y"}


# ---------------------------------------------------------------------------
# Missing dependency reference
# ---------------------------------------------------------------------------


class TestMissingDependency:
    def test_depends_on_unregistered_raises_on_sort(self) -> None:
        from brimley.core.di import Depends

        container = BrimleyContainer()

        def svc(x=Depends("unregistered_dep")) -> str:
            return "s"

        _register(container, "_r.miss1", "svc", svc)
        resolver = DependencyResolver(container)
        with pytest.raises(ProviderResolutionError, match="'unregistered_dep'"):
            resolver.topological_sort(["svc"])


# ---------------------------------------------------------------------------
# BrimleyContext field on BrimleyContext
# ---------------------------------------------------------------------------


class TestBrimleyContextContainerField:
    def test_container_field_defaults_to_none(self) -> None:
        from brimley.core.context import BrimleyContext

        ctx = BrimleyContext()
        assert ctx.container is None

    def test_container_field_can_be_set(self) -> None:
        from brimley.core.context import BrimleyContext

        ctx = BrimleyContext()
        container = BrimleyContainer()
        ctx.container = container
        assert ctx.container is container
