"""Tests for B08-S1: ProviderMetadata, LifecycleHookMetadata, and Depends."""
import pytest
from pydantic import ValidationError

from brimley.core.models import LifecycleHookMetadata, ProviderMetadata
from brimley.core.di import Depends


# ---------------------------------------------------------------------------
# ProviderMetadata
# ---------------------------------------------------------------------------


class TestProviderMetadata:
    def test_minimal_valid_model(self):
        m = ProviderMetadata(module_path="my.module", func_name="get_client")
        assert m.name is None
        assert m.scope == "singleton"
        assert m.eager is False
        assert m.module_path == "my.module"
        assert m.func_name == "get_client"
        assert m.handler is None

    def test_fully_specified(self):
        m = ProviderMetadata(
            name="http_client",
            scope="request",
            eager=True,
            module_path="app.providers",
            func_name="make_client",
            handler="app.providers.make_client",
        )
        assert m.name == "http_client"
        assert m.scope == "request"
        assert m.eager is True
        assert m.handler == "app.providers.make_client"

    def test_scope_defaults_to_singleton(self):
        m = ProviderMetadata(module_path="a.b", func_name="f")
        assert m.scope == "singleton"

    def test_scope_singleton_explicit(self):
        m = ProviderMetadata(scope="singleton", module_path="a.b", func_name="f")
        assert m.scope == "singleton"

    def test_scope_request(self):
        m = ProviderMetadata(scope="request", module_path="a.b", func_name="f")
        assert m.scope == "request"

    def test_scope_invalid(self):
        with pytest.raises(ValidationError):
            ProviderMetadata(scope="transient", module_path="a.b", func_name="f")

    def test_eager_defaults_false(self):
        m = ProviderMetadata(module_path="a.b", func_name="f")
        assert m.eager is False

    def test_eager_true(self):
        m = ProviderMetadata(eager=True, module_path="a.b", func_name="f")
        assert m.eager is True

    def test_module_path_required(self):
        with pytest.raises(ValidationError):
            ProviderMetadata(func_name="f")

    def test_func_name_required(self):
        with pytest.raises(ValidationError):
            ProviderMetadata(module_path="a.b")

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ProviderMetadata(module_path="a.b", func_name="f", unknown_field="x")

    def test_handler_dotted_string(self):
        m = ProviderMetadata(
            module_path="pkg.mod",
            func_name="factory",
            handler="pkg.mod.factory",
        )
        assert m.handler == "pkg.mod.factory"

    def test_equality(self):
        m1 = ProviderMetadata(module_path="a.b", func_name="f")
        m2 = ProviderMetadata(module_path="a.b", func_name="f")
        assert m1 == m2

    def test_serialization(self):
        m = ProviderMetadata(
            name="client",
            scope="singleton",
            eager=False,
            module_path="app.providers",
            func_name="get_client",
        )
        d = m.model_dump()
        assert d["name"] == "client"
        assert d["scope"] == "singleton"
        assert d["eager"] is False
        assert d["module_path"] == "app.providers"
        assert d["func_name"] == "get_client"
        assert d["handler"] is None


# ---------------------------------------------------------------------------
# LifecycleHookMetadata
# ---------------------------------------------------------------------------


class TestLifecycleHookMetadata:
    def test_on_startup_minimal(self):
        m = LifecycleHookMetadata(
            hook_type="on_startup",
            module_path="app.hooks",
            func_name="init_db",
        )
        assert m.hook_type == "on_startup"
        assert m.module_path == "app.hooks"
        assert m.func_name == "init_db"
        assert m.handler is None

    def test_on_shutdown_minimal(self):
        m = LifecycleHookMetadata(
            hook_type="on_shutdown",
            module_path="app.hooks",
            func_name="close_connections",
        )
        assert m.hook_type == "on_shutdown"

    def test_with_handler(self):
        m = LifecycleHookMetadata(
            hook_type="on_startup",
            module_path="app.hooks",
            func_name="init_db",
            handler="app.hooks.init_db",
        )
        assert m.handler == "app.hooks.init_db"

    def test_hook_type_invalid(self):
        with pytest.raises(ValidationError):
            LifecycleHookMetadata(
                hook_type="on_ready",
                module_path="app.hooks",
                func_name="f",
            )

    def test_hook_type_required(self):
        with pytest.raises(ValidationError):
            LifecycleHookMetadata(module_path="app.hooks", func_name="f")

    def test_module_path_required(self):
        with pytest.raises(ValidationError):
            LifecycleHookMetadata(hook_type="on_startup", func_name="f")

    def test_func_name_required(self):
        with pytest.raises(ValidationError):
            LifecycleHookMetadata(hook_type="on_startup", module_path="app.hooks")

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            LifecycleHookMetadata(
                hook_type="on_startup",
                module_path="app.hooks",
                func_name="f",
                unknown="x",
            )

    def test_equality(self):
        m1 = LifecycleHookMetadata(
            hook_type="on_startup", module_path="a.b", func_name="f"
        )
        m2 = LifecycleHookMetadata(
            hook_type="on_startup", module_path="a.b", func_name="f"
        )
        assert m1 == m2

    def test_serialization(self):
        m = LifecycleHookMetadata(
            hook_type="on_shutdown",
            module_path="app.lifecycle",
            func_name="teardown",
        )
        d = m.model_dump()
        assert d["hook_type"] == "on_shutdown"
        assert d["module_path"] == "app.lifecycle"
        assert d["func_name"] == "teardown"
        assert d["handler"] is None


# ---------------------------------------------------------------------------
# Depends
# ---------------------------------------------------------------------------


class TestDepends:
    def test_depends_with_callable(self):
        def get_client():
            pass

        d = Depends(get_client)
        assert d.provider_name == "get_client"

    def test_depends_with_string(self):
        d = Depends("my_provider")
        assert d.provider_name == "my_provider"

    def test_depends_stores_dependency_callable(self):
        def get_client():
            pass

        d = Depends(get_client)
        assert d._dependency is get_client

    def test_depends_repr_callable(self):
        def get_client():
            pass

        d = Depends(get_client)
        assert repr(d) == "Depends('get_client')"

    def test_depends_repr_string(self):
        d = Depends("http_client")
        assert repr(d) == "Depends('http_client')"

    def test_depends_equality_same_name(self):
        def get_client():
            pass

        d1 = Depends(get_client)
        d2 = Depends("get_client")
        assert d1 == d2

    def test_depends_equality_different_names(self):
        d1 = Depends("provider_a")
        d2 = Depends("provider_b")
        assert d1 != d2

    def test_depends_hashable(self):
        d = Depends("provider_a")
        s = {d}
        assert len(s) == 1

    def test_depends_invalid_type(self):
        with pytest.raises(TypeError):
            Depends(42)

    def test_depends_usable_as_default_value(self):
        def get_db():
            pass

        def my_function(conn=Depends(get_db)):
            pass

        import inspect

        sig = inspect.signature(my_function)
        default = sig.parameters["conn"].default
        assert isinstance(default, Depends)
        assert default.provider_name == "get_db"

    def test_depends_with_async_callable(self):
        async def get_async_client():
            pass

        d = Depends(get_async_client)
        assert d.provider_name == "get_async_client"
