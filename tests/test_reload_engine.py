from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from brimley.core.models import TemplateFunction
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
    assert "existing" in context.functions
    assert "broken_candidate" not in context.functions
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
    assert "existing_tool" in context.functions
    assert "new_tool" not in context.functions
    assert result.summary.tools == 1
    assert any(diag.message.startswith("[functions]") for diag in result.diagnostics)
