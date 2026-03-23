"""Tests for B08-S2 (AST detection of DI decorators) and B08-S3 (Scanner extension)."""
import textwrap
from pathlib import Path

import pytest

from brimley.core.models import LifecycleHookMetadata, ProviderMetadata
from brimley.discovery.python_parser import parse_python_file
from brimley.discovery.scanner import BrimleyScanResult, Scanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_py(tmp_path: Path, name: str, source: str) -> Path:
    """Write a Python source file inside *tmp_path* and return its path."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(source))
    return p


# ---------------------------------------------------------------------------
# B08-S2: parse_python_file — @provider AST detection
# ---------------------------------------------------------------------------


class TestParseProviderBareDecorator:
    def test_bare_provider_defaults(self, tmp_path):
        f = write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider
            def get_client():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        p = items[0]
        assert isinstance(p, ProviderMetadata)
        assert p.func_name == "get_client"
        assert p.name is None
        assert p.scope == "singleton"
        assert p.eager is False
        assert p.handler is not None
        assert p.handler.endswith(".get_client")

    def test_bare_provider_async_def(self, tmp_path):
        f = write_py(
            tmp_path,
            "aprov.py",
            """\
            from brimley import provider

            @provider
            async def get_db():
                yield None
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        p = items[0]
        assert isinstance(p, ProviderMetadata)
        assert p.func_name == "get_db"


class TestParseProviderConfiguredDecorator:
    def test_scope_request(self, tmp_path):
        f = write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider(scope="request")
            def per_request_client():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        p = items[0]
        assert isinstance(p, ProviderMetadata)
        assert p.scope == "request"
        assert p.eager is False

    def test_eager_true(self, tmp_path):
        f = write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider(eager=True)
            def warmup_cache():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        p = items[0]
        assert isinstance(p, ProviderMetadata)
        assert p.eager is True
        assert p.scope == "singleton"

    def test_custom_name(self, tmp_path):
        f = write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider(name="http_client", scope="singleton", eager=False)
            def make_client():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        p = items[0]
        assert isinstance(p, ProviderMetadata)
        assert p.name == "http_client"
        assert p.func_name == "make_client"

    def test_all_kwargs(self, tmp_path):
        f = write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider(name="db", scope="request", eager=True)
            def db_session():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        p = items[0]
        assert isinstance(p, ProviderMetadata)
        assert p.name == "db"
        assert p.scope == "request"
        assert p.eager is True


class TestParseMultipleProviders:
    def test_two_providers_in_file(self, tmp_path):
        f = write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider
            def get_client():
                pass

            @provider(scope="request")
            def get_session():
                pass
            """,
        )
        items = parse_python_file(f)
        providers = [i for i in items if isinstance(i, ProviderMetadata)]
        assert len(providers) == 2
        names = {p.func_name for p in providers}
        assert names == {"get_client", "get_session"}

    def test_provider_and_function_in_same_file(self, tmp_path):
        f = write_py(
            tmp_path,
            "mixed.py",
            """\
            from brimley import function, provider

            @provider
            def get_client():
                pass

            @function
            def do_work() -> str:
                return "ok"
            """,
        )
        from brimley.core.models import PythonFunction

        items = parse_python_file(f)
        providers = [i for i in items if isinstance(i, ProviderMetadata)]
        functions = [i for i in items if isinstance(i, PythonFunction)]
        assert len(providers) == 1
        assert len(functions) == 1


# ---------------------------------------------------------------------------
# B08-S2: parse_python_file — @on_startup / @on_shutdown AST detection
# ---------------------------------------------------------------------------


class TestParseOnStartupShutdown:
    def test_bare_on_startup(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            from brimley import on_startup

            @on_startup
            def init_db():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        h = items[0]
        assert isinstance(h, LifecycleHookMetadata)
        assert h.hook_type == "on_startup"
        assert h.func_name == "init_db"
        assert h.handler is not None
        assert h.handler.endswith(".init_db")

    def test_bare_on_shutdown(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            from brimley import on_shutdown

            @on_shutdown
            def close_connections():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        h = items[0]
        assert isinstance(h, LifecycleHookMetadata)
        assert h.hook_type == "on_shutdown"
        assert h.func_name == "close_connections"

    def test_on_startup_empty_call(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            from brimley import on_startup

            @on_startup()
            def warmup():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        h = items[0]
        assert isinstance(h, LifecycleHookMetadata)
        assert h.hook_type == "on_startup"
        assert h.func_name == "warmup"

    def test_on_shutdown_empty_call(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            from brimley import on_shutdown

            @on_shutdown()
            def teardown():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        h = items[0]
        assert isinstance(h, LifecycleHookMetadata)
        assert h.hook_type == "on_shutdown"

    def test_async_on_startup(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            from brimley import on_startup

            @on_startup
            async def async_init():
                pass
            """,
        )
        items = parse_python_file(f)
        assert len(items) == 1
        h = items[0]
        assert isinstance(h, LifecycleHookMetadata)
        assert h.hook_type == "on_startup"
        assert h.func_name == "async_init"

    def test_mixed_hooks_in_file(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            from brimley import on_startup, on_shutdown

            @on_startup
            def startup_hook():
                pass

            @on_shutdown
            def shutdown_hook():
                pass
            """,
        )
        items = parse_python_file(f)
        hooks = [i for i in items if isinstance(i, LifecycleHookMetadata)]
        assert len(hooks) == 2
        types = [h.hook_type for h in hooks]
        assert "on_startup" in types
        assert "on_shutdown" in types


class TestParseNoDIDecorators:
    def test_plain_file_returns_empty(self, tmp_path):
        f = write_py(
            tmp_path,
            "plain.py",
            """\
            def helper():
                pass
            """,
        )
        items = parse_python_file(f)
        providers = [i for i in items if isinstance(i, ProviderMetadata)]
        hooks = [i for i in items if isinstance(i, LifecycleHookMetadata)]
        assert providers == []
        assert hooks == []

    def test_function_only_file_no_providers_or_hooks(self, tmp_path):
        f = write_py(
            tmp_path,
            "funcs.py",
            """\
            from brimley import function

            @function
            def greet(name: str) -> str:
                return f"Hello {name}"
            """,
        )
        items = parse_python_file(f)
        providers = [i for i in items if isinstance(i, ProviderMetadata)]
        hooks = [i for i in items if isinstance(i, LifecycleHookMetadata)]
        assert providers == []
        assert hooks == []


# ---------------------------------------------------------------------------
# B08-S2: qualified decorator names (brimley.provider etc.)
# ---------------------------------------------------------------------------


class TestQualifiedDecoratorNames:
    def test_qualified_provider(self, tmp_path):
        f = write_py(
            tmp_path,
            "providers.py",
            """\
            import brimley

            @brimley.provider
            def get_client():
                pass
            """,
        )
        items = parse_python_file(f)
        providers = [i for i in items if isinstance(i, ProviderMetadata)]
        assert len(providers) == 1
        assert providers[0].func_name == "get_client"

    def test_qualified_on_startup(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            import brimley

            @brimley.on_startup
            def init():
                pass
            """,
        )
        items = parse_python_file(f)
        hooks = [i for i in items if isinstance(i, LifecycleHookMetadata)]
        assert len(hooks) == 1
        assert hooks[0].hook_type == "on_startup"

    def test_qualified_on_shutdown(self, tmp_path):
        f = write_py(
            tmp_path,
            "hooks.py",
            """\
            import brimley

            @brimley.on_shutdown
            def cleanup():
                pass
            """,
        )
        items = parse_python_file(f)
        hooks = [i for i in items if isinstance(i, LifecycleHookMetadata)]
        assert len(hooks) == 1
        assert hooks[0].hook_type == "on_shutdown"


# ---------------------------------------------------------------------------
# B08-S3: Scanner.scan() — BrimleyScanResult providers and lifecycle_hooks
# ---------------------------------------------------------------------------


class TestScannerProviders:
    def test_providers_field_populated(self, tmp_path):
        write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider
            def get_client():
                pass
            """,
        )
        result = Scanner(tmp_path).scan()
        assert isinstance(result, BrimleyScanResult)
        assert len(result.providers) == 1
        p = result.providers[0]
        assert isinstance(p, ProviderMetadata)
        assert p.func_name == "get_client"

    def test_lifecycle_hooks_field_populated(self, tmp_path):
        write_py(
            tmp_path,
            "hooks.py",
            """\
            from brimley import on_startup, on_shutdown

            @on_startup
            def init():
                pass

            @on_shutdown
            def teardown():
                pass
            """,
        )
        result = Scanner(tmp_path).scan()
        assert len(result.lifecycle_hooks) == 2
        types = {h.hook_type for h in result.lifecycle_hooks}
        assert types == {"on_startup", "on_shutdown"}

    def test_providers_empty_when_none_declared(self, tmp_path):
        write_py(
            tmp_path,
            "funcs.py",
            """\
            from brimley import function

            @function
            def greet(name: str) -> str:
                return f"Hello {name}"
            """,
        )
        result = Scanner(tmp_path).scan()
        assert result.providers == []
        assert result.lifecycle_hooks == []
        assert len(result.functions) == 1

    def test_scan_result_has_providers_lifecycle_hooks_fields(self, tmp_path):
        """BrimleyScanResult has the new fields even with no items."""
        result = Scanner(tmp_path).scan()
        assert hasattr(result, "providers")
        assert hasattr(result, "lifecycle_hooks")
        assert result.providers == []
        assert result.lifecycle_hooks == []


class TestScannerDuplicateProvider:
    def test_duplicate_provider_name_via_func_name(self, tmp_path):
        (tmp_path / "a.py").write_text(
            textwrap.dedent(
                """\
                from brimley import provider

                @provider
                def get_client():
                    pass
                """
            )
        )
        (tmp_path / "b.py").write_text(
            textwrap.dedent(
                """\
                from brimley import provider

                @provider
                def get_client():
                    pass
                """
            )
        )
        result = Scanner(tmp_path).scan()
        dup = [d for d in result.diagnostics if d.error_code == "ERR_DUPLICATE_PROVIDER"]
        assert len(dup) == 1
        assert "get_client" in dup[0].message
        # Only the first registration survives
        assert len(result.providers) == 1

    def test_duplicate_provider_name_via_custom_name(self, tmp_path):
        (tmp_path / "a.py").write_text(
            textwrap.dedent(
                """\
                from brimley import provider

                @provider(name="my_client")
                def make_client_a():
                    pass
                """
            )
        )
        (tmp_path / "b.py").write_text(
            textwrap.dedent(
                """\
                from brimley import provider

                @provider(name="my_client")
                def make_client_b():
                    pass
                """
            )
        )
        result = Scanner(tmp_path).scan()
        dup = [d for d in result.diagnostics if d.error_code == "ERR_DUPLICATE_PROVIDER"]
        assert len(dup) == 1
        assert "my_client" in dup[0].message

    def test_no_duplicate_for_unique_providers(self, tmp_path):
        write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider
            def get_client():
                pass

            @provider
            def get_db():
                pass
            """,
        )
        result = Scanner(tmp_path).scan()
        dup = [d for d in result.diagnostics if d.error_code == "ERR_DUPLICATE_PROVIDER"]
        assert dup == []
        assert len(result.providers) == 2


class TestScannerProviderInvalidName:
    def test_invalid_provider_name_func_name(self, tmp_path):
        write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider
            def _invalid():
                pass
            """,
        )
        result = Scanner(tmp_path).scan()
        err = [d for d in result.diagnostics if d.error_code == "ERR_INVALID_NAME"]
        assert len(err) == 1
        assert "_invalid" in err[0].message
        assert result.providers == []

    def test_invalid_provider_custom_name(self, tmp_path):
        write_py(
            tmp_path,
            "providers.py",
            """\
            from brimley import provider

            @provider(name="123bad")
            def some_provider():
                pass
            """,
        )
        result = Scanner(tmp_path).scan()
        err = [d for d in result.diagnostics if d.error_code == "ERR_INVALID_NAME"]
        assert len(err) == 1
        assert result.providers == []


class TestScannerProviderShadowsFunction:
    def test_provider_shadows_function_warning(self, tmp_path):
        # Warning is emitted regardless of which file is scanned first (bidirectional check).
        (tmp_path / "funcs.py").write_text(
            textwrap.dedent(
                """\
                from brimley import function

                @function
                def get_client() -> str:
                    return "ok"
                """
            )
        )
        (tmp_path / "providers.py").write_text(
            textwrap.dedent(
                """\
                from brimley import provider

                @provider
                def get_client():
                    pass
                """
            )
        )
        result = Scanner(tmp_path).scan()
        warn = [d for d in result.diagnostics if d.error_code == "ERR_PROVIDER_SHADOWS_FUNCTION"]
        assert len(warn) == 1
        assert warn[0].severity == "warning"
        assert "get_client" in warn[0].message
        # Both the function and provider are still registered (different namespaces)
        assert len(result.functions) == 1
        assert len(result.providers) == 1


class TestScannerExistingBehaviorUnaffected:
    """Regression: existing function/entity scanning still works after B08-S3 changes."""

    def test_sql_function_still_scanned(self, tmp_path):
        (tmp_path / "query.sql").write_text(
            """\
/*
---
name: get_users
type: sql_function
return_shape: void
---
*/
SELECT 1;
"""
        )
        result = Scanner(tmp_path).scan()
        names = {f.name for f in result.functions}
        assert "get_users" in names
        assert result.providers == []
        assert result.lifecycle_hooks == []

    def test_python_function_and_providers_coexist(self, tmp_path):
        write_py(
            tmp_path,
            "app.py",
            """\
            from brimley import function, provider, on_startup

            @provider
            def get_db():
                pass

            @on_startup
            def init():
                pass

            @function
            def query_data() -> str:
                return "data"
            """,
        )
        result = Scanner(tmp_path).scan()
        assert len(result.functions) == 1
        assert result.functions[0].name == "query_data"
        assert len(result.providers) == 1
        assert result.providers[0].func_name == "get_db"
        assert len(result.lifecycle_hooks) == 1
        assert result.lifecycle_hooks[0].hook_type == "on_startup"
        assert result.diagnostics == []

    def test_duplicate_function_diagnostic_still_works(self, tmp_path):
        (tmp_path / "a.sql").write_text(
            """\
/*
---
name: get_user
type: sql_function
return_shape: void
---
*/
SELECT 1;
"""
        )
        (tmp_path / "b.sql").write_text(
            """\
/*
---
name: get_user
type: sql_function
return_shape: void
---
*/
SELECT 1;
"""
        )
        result = Scanner(tmp_path).scan()
        dup = [d for d in result.diagnostics if d.error_code == "ERR_DUPLICATE_NAME"]
        assert len(dup) == 1
