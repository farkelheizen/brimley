import pytest

from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from types import ModuleType

from brimley.core.models import PythonFunction, TemplateFunction
from brimley.discovery.scanner import BrimleyScanResult
from brimley.runtime.reload_contracts import ReloadDomain
from brimley.runtime.reload_engine import PartitionedReloadEngine
from brimley.utils.diagnostics import BrimleyDiagnostic


def test_reload_engine_partitions_mcp_tools_from_functions():
    engine = PartitionedReloadEngine()
    scan_result = BrimleyScanResult(
        functions=[
            TemplateFunction(
                name="tool_func",
                type="template_function",
                return_shape="string",
                template_body="hello",
                mcp={"type": "tool"},
            ),
            TemplateFunction(
                name="regular_func",
                type="template_function",
                return_shape="string",
                template_body="hello",
            ),
        ],
        entities=[Entity(name="Customer")],
    )

    partitions = engine.partition_scan_result(scan_result)

    assert len(partitions.functions) == 2
    assert len(partitions.entities) == 1
    assert [f.name for f in partitions.mcp_tools] == ["tool_func"]


def test_reload_engine_dependency_graph_contract():
    graph = PartitionedReloadEngine().dependency_graph()

    assert graph[ReloadDomain.ENTITIES] == []
    assert graph[ReloadDomain.FUNCTIONS] == [ReloadDomain.ENTITIES]
    assert graph[ReloadDomain.MCP_TOOLS] == [ReloadDomain.FUNCTIONS]


def test_reload_engine_apply_successful_reload_swaps_domains_in_order():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="old_func",
            type="template_function",
            return_shape="string",
            template_body="old",
        )
    )

    engine = PartitionedReloadEngine()
    scan_result = BrimleyScanResult(
        functions=[
            TemplateFunction(
                name="new_tool",
                type="template_function",
                return_shape="string",
                template_body="new",
                mcp={"type": "tool"},
            )
        ],
        entities=[Entity(name="Order")],
    )

    partitions = engine.partition_scan_result(scan_result)
    summary = engine.apply_successful_reload(context, partitions)

    assert "old_func" not in context.functions
    assert "new_tool" in context.functions
    assert "Order" in context.entities
    assert "ContentBlock" in context.entities
    assert "PromptMessage" in context.entities
    assert summary.functions == 1
    assert summary.tools == 1
    assert summary.entities == len(context.entities)


def test_reload_engine_policy_keeps_functions_when_function_domain_has_errors():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="existing",
            type="template_function",
            return_shape="string",
            template_body="existing",
        )
    )

    engine = PartitionedReloadEngine()
    scan_result = BrimleyScanResult(
        functions=[
            TemplateFunction(
                name="broken_candidate",
                type="template_function",
                return_shape="string",
                template_body="new",
            )
        ],
        entities=[Entity(name="Invoice")],
        diagnostics=[
            BrimleyDiagnostic(
                file_path="broken.md",
                error_code="ERR_PARSE_FAILURE",
                severity="error",
                message="invalid frontmatter",
            )
        ],
    )

    result = engine.apply_reload_with_policy(context, scan_result)

    assert ReloadDomain.FUNCTIONS in result.blocked_domains
    assert ReloadDomain.MCP_TOOLS in result.blocked_domains
    assert "existing" not in context.functions
    assert "broken_candidate" in context.functions
    assert "Invoice" in context.entities
    assert any(diag.message.startswith("[functions]") for diag in result.diagnostics)


def test_reload_engine_policy_blocks_everything_when_entity_domain_has_errors():
    context = BrimleyContext()
    context.entities.register(Entity(name="KeepMe"))
    context.functions.register(
        TemplateFunction(
            name="keep_func",
            type="template_function",
            return_shape="string",
            template_body="old",
        )
    )

    engine = PartitionedReloadEngine()
    scan_result = BrimleyScanResult(
        functions=[
            TemplateFunction(
                name="new_func",
                type="template_function",
                return_shape="string",
                template_body="new",
            )
        ],
        entities=[Entity(name="NewEntity")],
        diagnostics=[
            BrimleyDiagnostic(
                file_path="entity.yaml",
                error_code="ERR_PARSE_FAILURE",
                severity="critical",
                message="entity parse failure",
            )
        ],
    )

    result = engine.apply_reload_with_policy(context, scan_result)

    assert ReloadDomain.ENTITIES in result.blocked_domains
    assert ReloadDomain.FUNCTIONS in result.blocked_domains
    assert ReloadDomain.MCP_TOOLS in result.blocked_domains
    assert "keep_func" in context.functions
    assert "KeepMe" in context.entities
    assert any(diag.message.startswith("[entities]") for diag in result.diagnostics)
    assert any(diag.error_code == "ERR_RELOAD_DOMAIN_BLOCKED" for diag in result.diagnostics)


def test_reload_engine_policy_allows_full_swap_on_warning_only_diagnostics():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="legacy",
            type="template_function",
            return_shape="string",
            template_body="old",
        )
    )

    engine = PartitionedReloadEngine()
    scan_result = BrimleyScanResult(
        functions=[
            TemplateFunction(
                name="fresh",
                type="template_function",
                return_shape="string",
                template_body="new",
            )
        ],
        entities=[Entity(name="Customer")],
        diagnostics=[
            BrimleyDiagnostic(
                file_path="fresh.md",
                error_code="WARN_STYLE",
                severity="warning",
                message="non-blocking warning",
            )
        ],
    )

    result = engine.apply_reload_with_policy(context, scan_result)

    assert result.blocked_domains == []
    assert "legacy" not in context.functions
    assert "fresh" in context.functions
    assert "Customer" in context.entities
    assert any(diag.message.startswith("[functions]") for diag in result.diagnostics)


def test_reload_engine_policy_rolls_back_downstream_domains_only():
    context = BrimleyContext()
    context.functions.register(
        TemplateFunction(
            name="existing_tool",
            type="template_function",
            return_shape="string",
            template_body="old",
            mcp={"type": "tool"},
        )
    )

    engine = PartitionedReloadEngine()
    scan_result = BrimleyScanResult(
        functions=[
            TemplateFunction(
                name="new_tool",
                type="template_function",
                return_shape="string",
                template_body="new",
                mcp={"type": "tool"},
            )
        ],
        entities=[Entity(name="Address")],
        diagnostics=[
            BrimleyDiagnostic(
                file_path="new_tool.md",
                error_code="ERR_PARSE_FAILURE",
                severity="error",
                message="template parse failure",
            )
        ],
    )

    result = engine.apply_reload_with_policy(context, scan_result)

    assert ReloadDomain.ENTITIES not in result.blocked_domains
    assert ReloadDomain.FUNCTIONS in result.blocked_domains
    assert ReloadDomain.MCP_TOOLS in result.blocked_domains
    assert "Address" in context.entities
    assert "existing_tool" not in context.functions
    assert "new_tool" in context.functions
    assert result.summary.tools == 1
    assert any(diag.message.startswith("[functions]") for diag in result.diagnostics)


def test_reload_engine_rehydrates_only_reload_enabled_python_modules(monkeypatch):
    engine = PartitionedReloadEngine()

    reloaded_modules: list[str] = []
    invalidate_calls = {"count": 0}
    checkcache_calls = {"count": 0}

    module_a = ModuleType("pkg.a")
    module_b = ModuleType("pkg.b")

    def fake_invalidate() -> None:
        invalidate_calls["count"] += 1

    def fake_import_module(name: str):
        if name == "pkg.a":
            return module_a
        if name == "pkg.b":
            return module_b
        raise ModuleNotFoundError(name)

    def fake_reload(module):
        reloaded_modules.append(module.__name__)
        return module

    def fake_checkcache() -> None:
        checkcache_calls["count"] += 1

    monkeypatch.setattr("brimley.runtime.reload_engine.importlib.invalidate_caches", fake_invalidate)
    monkeypatch.setattr("brimley.runtime.reload_engine.importlib.import_module", fake_import_module)
    monkeypatch.setattr("brimley.runtime.reload_engine.importlib.reload", fake_reload)
    monkeypatch.setattr("brimley.runtime.reload_engine.linecache.checkcache", fake_checkcache)

    functions = [
        PythonFunction(
            name="f1",
            type="python_function",
            handler="pkg.a.one",
            return_shape="void",
            reload=True,
        ),
        PythonFunction(
            name="f2",
            type="python_function",
            handler="pkg.a.two",
            return_shape="void",
            reload=False,
        ),
        PythonFunction(
            name="f3",
            type="python_function",
            handler="pkg.b.three",
            return_shape="void",
            reload=False,
        ),
    ]

    engine._rehydrate_python_modules(BrimleyContext(), functions)

    assert reloaded_modules == ["pkg.a"]
    assert invalidate_calls["count"] == 1
    assert checkcache_calls["count"] == 1


def test_reload_engine_policy_rehydrates_only_when_function_domain_swaps(monkeypatch):
    context = BrimleyContext()
    engine = PartitionedReloadEngine()

    calls = {"count": 0}

    def fake_rehydrate(_context, _functions):
        calls["count"] += 1

    monkeypatch.setattr(engine, "_rehydrate_python_modules", fake_rehydrate)

    success_scan = BrimleyScanResult(
        functions=[
            PythonFunction(
                name="reloadable",
                type="python_function",
                handler="pkg.mod.reloadable",
                return_shape="void",
                reload=True,
            )
        ],
        entities=[Entity(name="EntityOk")],
        diagnostics=[],
    )

    result_success = engine.apply_reload_with_policy(context, success_scan)

    assert result_success.blocked_domains == []
    assert calls["count"] == 1

    failure_scan = BrimleyScanResult(
        functions=[
            PythonFunction(
                name="broken",
                type="python_function",
                handler="pkg.mod.broken",
                return_shape="void",
                reload=True,
            )
        ],
        entities=[Entity(name="EntityStillOk")],
        diagnostics=[
            BrimleyDiagnostic(
                file_path="broken.py",
                error_code="ERR_PARSE_FAILURE",
                severity="error",
                message="function parse failed",
            )
        ],
    )

    result_failure = engine.apply_reload_with_policy(context, failure_scan)

    assert ReloadDomain.FUNCTIONS in result_failure.blocked_domains
    assert calls["count"] == 2


def test_reload_engine_quarantines_changed_broken_function_without_stale_fallback():
    context = BrimleyContext()
    context.app["root_dir"] = "/project"
    context.functions.register(
        TemplateFunction(
            name="hello",
            type="template_function",
            return_shape="string",
            template_body="old",
            canonical_id="function:hello.md:hello",
        )
    )
    context.functions.register(
        TemplateFunction(
            name="stable",
            type="template_function",
            return_shape="string",
            template_body="stable-old",
            canonical_id="function:stable.md:stable",
        )
    )

    engine = PartitionedReloadEngine()
    scan_result = BrimleyScanResult(
        functions=[
            TemplateFunction(
                name="stable",
                type="template_function",
                return_shape="string",
                template_body="stable-new",
                canonical_id="function:stable.md:stable",
            ),
            TemplateFunction(
                name="fresh",
                type="template_function",
                return_shape="string",
                template_body="fresh",
                canonical_id="function:fresh.md:fresh",
            ),
        ],
        diagnostics=[
            BrimleyDiagnostic(
                file_path="/project/hello.md",
                error_code="ERR_PARSE_FAILURE",
                severity="error",
                message="invalid frontmatter",
            )
        ],
    )

    result = engine.apply_reload_with_policy(context, scan_result)

    assert ReloadDomain.FUNCTIONS in result.blocked_domains
    assert "fresh" in context.functions
    assert "stable" in context.functions
    assert "hello" in context.functions
    with pytest.raises(KeyError, match="quarantined"):
        context.functions.get("hello")
