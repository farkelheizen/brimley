from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from brimley.core.models import BrimleyFunction
from brimley.core.registry import Registry
from brimley.discovery.scanner import BrimleyScanResult
from brimley.runtime.reload_contracts import RELOAD_DOMAIN_ORDER, ReloadDomain, ReloadSummary


@dataclass(frozen=True)
class ReloadPartitions:
    """Partitioned discovery artifacts for one reload cycle."""

    entities: List[Entity]
    functions: List[BrimleyFunction]
    mcp_tools: List[BrimleyFunction]


class PartitionedReloadEngine:
    """Applies partitioned reload pipeline with explicit dependency ordering."""

    BUILTIN_ENTITY_NAMES = ("ContentBlock", "PromptMessage")

    def dependency_graph(self) -> Dict[ReloadDomain, List[ReloadDomain]]:
        """Return dependency graph for reload domains."""

        return {
            ReloadDomain.ENTITIES: [],
            ReloadDomain.FUNCTIONS: [ReloadDomain.ENTITIES],
            ReloadDomain.MCP_TOOLS: [ReloadDomain.FUNCTIONS],
        }

    def partition_scan_result(self, scan_result: BrimleyScanResult) -> ReloadPartitions:
        """Partition scan output into entities, functions, and MCP tool domains."""

        mcp_tools = [
            func
            for func in scan_result.functions
            if getattr(getattr(func, "mcp", None), "type", None) == "tool"
        ]
        return ReloadPartitions(
            entities=list(scan_result.entities),
            functions=list(scan_result.functions),
            mcp_tools=mcp_tools,
        )

    def apply_successful_reload(self, context: BrimleyContext, partitions: ReloadPartitions) -> ReloadSummary:
        """Apply reload swaps in dependency order for a successful cycle."""

        for domain in RELOAD_DOMAIN_ORDER:
            if domain == ReloadDomain.ENTITIES:
                context.entities = self._build_entities_registry(context, partitions.entities)
            elif domain == ReloadDomain.FUNCTIONS:
                context.functions = self._build_functions_registry(partitions.functions)
            elif domain == ReloadDomain.MCP_TOOLS:
                # Phase 1 pipeline: tool domain is derived and summarized here.
                # Actual MCP refresh orchestration is implemented in a later phase.
                pass

        return ReloadSummary(
            entities=len(context.entities),
            functions=len(context.functions),
            tools=len(partitions.mcp_tools),
        )

    def _build_entities_registry(self, context: BrimleyContext, entities: List[Entity]) -> Registry[Entity]:
        next_entities: Registry[Entity] = Registry()

        for builtin_name in self.BUILTIN_ENTITY_NAMES:
            if builtin_name in context.entities:
                next_entities.register(context.entities.get(builtin_name))

        next_entities.register_all(entities)
        return next_entities

    def _build_functions_registry(self, functions: List[BrimleyFunction]) -> Registry[BrimleyFunction]:
        next_functions: Registry[BrimleyFunction] = Registry()
        next_functions.register_all(functions)
        return next_functions
