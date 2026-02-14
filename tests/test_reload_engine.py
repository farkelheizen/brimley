from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from brimley.core.models import TemplateFunction
from brimley.discovery.scanner import BrimleyScanResult
from brimley.runtime.reload_contracts import ReloadDomain
from brimley.runtime.reload_engine import PartitionedReloadEngine


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
