from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import linecache
from pathlib import Path
import sys
from typing import Dict, List

from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from brimley.core.models import BrimleyFunction
from brimley.core.registry import Registry
from brimley.discovery.scanner import BrimleyScanResult
from brimley.runtime.reload_contracts import (
    RELOAD_DOMAIN_ORDER,
    DomainReloadInput,
    ReloadDomain,
    ReloadSummary,
    evaluate_domain_swap_policy,
    has_critical_diagnostics,
)
from brimley.utils.diagnostics import BrimleyDiagnostic


@dataclass(frozen=True)
class ReloadPartitions:
    """Partitioned discovery artifacts for one reload cycle."""

    entities: List[Entity]
    functions: List[BrimleyFunction]
    mcp_tools: List[BrimleyFunction]


@dataclass(frozen=True)
class ReloadApplicationResult:
    """Outcome of a policy-driven reload application."""

    summary: ReloadSummary
    blocked_domains: List[ReloadDomain]
    diagnostics: List[BrimleyDiagnostic]


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
                self._rehydrate_python_modules(context, partitions.functions)
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

    def apply_reload_with_policy(self, context: BrimleyContext, scan_result: BrimleyScanResult) -> ReloadApplicationResult:
        """Apply partitioned reload with domain-specific swap/rollback decisions."""

        partitions = self.partition_scan_result(scan_result)
        diagnostics_by_domain = self._classify_diagnostics(scan_result.diagnostics)

        decisions = evaluate_domain_swap_policy(
            {
                ReloadDomain.ENTITIES: DomainReloadInput(diagnostics=diagnostics_by_domain[ReloadDomain.ENTITIES]),
                ReloadDomain.FUNCTIONS: DomainReloadInput(diagnostics=diagnostics_by_domain[ReloadDomain.FUNCTIONS]),
                ReloadDomain.MCP_TOOLS: DomainReloadInput(diagnostics=diagnostics_by_domain[ReloadDomain.MCP_TOOLS]),
            }
        )

        if decisions[ReloadDomain.ENTITIES].can_swap:
            context.entities = self._build_entities_registry(context, partitions.entities)

        functions_has_critical = has_critical_diagnostics(diagnostics_by_domain[ReloadDomain.FUNCTIONS])
        function_partial_swap = (
            not decisions[ReloadDomain.FUNCTIONS].can_swap
            and decisions[ReloadDomain.ENTITIES].can_swap
            and functions_has_critical
        )

        if decisions[ReloadDomain.FUNCTIONS].can_swap or function_partial_swap:
            self._rehydrate_python_modules(context, partitions.functions)
            next_functions = self._build_functions_registry(partitions.functions)
            if function_partial_swap:
                for name, reason in self._quarantined_function_reasons(
                    context,
                    next_functions,
                    diagnostics_by_domain[ReloadDomain.FUNCTIONS],
                ).items():
                    next_functions.mark_quarantined(name, reason)

            context.functions = next_functions

        tools_count = (
            len(partitions.mcp_tools)
            if decisions[ReloadDomain.MCP_TOOLS].can_swap
            else self._count_current_tools(context)
        )

        blocked_domains = [domain for domain, decision in decisions.items() if not decision.can_swap]

        labeled_diagnostics: List[BrimleyDiagnostic] = []
        for domain in RELOAD_DOMAIN_ORDER:
            labeled_diagnostics.extend(self._label_domain_diagnostics(domain, diagnostics_by_domain[domain]))
            if not decisions[domain].can_swap and not diagnostics_by_domain[domain]:
                labeled_diagnostics.append(
                    BrimleyDiagnostic(
                        file_path="<runtime>",
                        error_code="ERR_RELOAD_DOMAIN_BLOCKED",
                        severity="warning",
                        message=f"[{domain.value}] {decisions[domain].blocked_reason}",
                    )
                )

        summary = ReloadSummary(
            entities=len(context.entities),
            functions=len(context.functions),
            tools=tools_count,
        )

        return ReloadApplicationResult(
            summary=summary,
            blocked_domains=blocked_domains,
            diagnostics=labeled_diagnostics,
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

    def _rehydrate_python_modules(self, context: BrimleyContext, functions: List[BrimleyFunction]) -> None:
        """Reload discovered Python modules for reload-enabled handlers."""
        module_reload_policy: Dict[str, bool] = {}
        import_roots = self._collect_import_roots(context)

        for function in functions:
            if getattr(function, "type", None) != "python_function":
                continue

            handler = getattr(function, "handler", None)
            if not isinstance(handler, str) or "." not in handler:
                continue

            module_name = handler.rsplit(".", 1)[0]
            should_reload = bool(getattr(function, "reload", True))
            module_reload_policy[module_name] = module_reload_policy.get(module_name, False) or should_reload

        importlib.invalidate_caches()

        for module_name, should_reload in module_reload_policy.items():
            if not should_reload:
                continue

            try:
                if import_roots:
                    with self._temporary_sys_path(import_roots):
                        module = importlib.import_module(module_name)
                        self._remove_cached_bytecode(module)
                        importlib.reload(module)
                else:
                    module = importlib.import_module(module_name)
                    self._remove_cached_bytecode(module)
                    importlib.reload(module)
            except Exception:
                continue

        linecache.checkcache()

    def _remove_cached_bytecode(self, module: object) -> None:
        cached_path = getattr(module, "__cached__", None)
        if not isinstance(cached_path, str):
            return

        try:
            cached_file = Path(cached_path)
            if cached_file.exists():
                cached_file.unlink()
        except Exception:
            return

    def _collect_import_roots(self, context: BrimleyContext) -> List[str]:
        roots: List[str] = []
        if not isinstance(context.app, dict):
            return roots

        for key in ("root_dir", "project_root", "root", "scan_root"):
            value = context.app.get(key)
            if value is None:
                continue
            path = Path(value).expanduser().resolve()
            path_str = str(path)
            if path.exists() and path_str not in roots:
                roots.append(path_str)

        return roots

    @contextmanager
    def _temporary_sys_path(self, roots: List[str]):
        inserted: List[str] = []
        for root in reversed(roots):
            if root not in sys.path:
                sys.path.insert(0, root)
                inserted.append(root)

        try:
            yield
        finally:
            for root in inserted:
                try:
                    sys.path.remove(root)
                except ValueError:
                    continue

    def _count_current_tools(self, context: BrimleyContext) -> int:
        return sum(1 for func in context.functions if getattr(getattr(func, "mcp", None), "type", None) == "tool")

    def _classify_diagnostics(
        self, diagnostics: List[BrimleyDiagnostic]
    ) -> Dict[ReloadDomain, List[BrimleyDiagnostic]]:
        by_domain: Dict[ReloadDomain, List[BrimleyDiagnostic]] = {
            ReloadDomain.ENTITIES: [],
            ReloadDomain.FUNCTIONS: [],
            ReloadDomain.MCP_TOOLS: [],
        }

        for diag in diagnostics:
            domain = self._domain_for_path(diag.file_path)
            by_domain[domain].append(diag)

        return by_domain

    def _domain_for_path(self, file_path: str) -> ReloadDomain:
        suffix = Path(file_path).suffix.lower()
        if suffix in {".yaml", ".yml"}:
            return ReloadDomain.ENTITIES
        return ReloadDomain.FUNCTIONS

    def _label_domain_diagnostics(
        self, domain: ReloadDomain, diagnostics: List[BrimleyDiagnostic]
    ) -> List[BrimleyDiagnostic]:
        return [
            BrimleyDiagnostic(
                file_path=diag.file_path,
                error_code=diag.error_code,
                severity=diag.severity,
                message=f"[{domain.value}] {diag.message}",
                suggestion=diag.suggestion,
                line_number=diag.line_number,
            )
            for diag in diagnostics
        ]

    def _quarantined_function_reasons(
        self,
        context: BrimleyContext,
        next_functions: Registry[BrimleyFunction],
        diagnostics: List[BrimleyDiagnostic],
    ) -> Dict[str, str]:
        relative_diag_paths = self._diagnostic_relative_paths(context, diagnostics)
        if not relative_diag_paths:
            return {}

        quarantined: Dict[str, str] = {}
        for function in context.functions:
            canonical_id = getattr(function, "canonical_id", None)
            if not isinstance(canonical_id, str) or not canonical_id.startswith("function:"):
                continue

            _, function_path, _ = canonical_id.split(":", 2)
            if function_path.lower() not in relative_diag_paths:
                continue

            if function.name in next_functions:
                continue

            quarantined[function.name] = "changed object failed validation during reload"

        return quarantined

    def _diagnostic_relative_paths(
        self,
        context: BrimleyContext,
        diagnostics: List[BrimleyDiagnostic],
    ) -> set[str]:
        root_dir_value = None
        if isinstance(context.app, dict):
            root_dir_value = context.app.get("root_dir")

        if not isinstance(root_dir_value, str):
            return set()

        root_path = Path(root_dir_value).expanduser().resolve()
        relative_paths: set[str] = set()
        for diag in diagnostics:
            try:
                diag_path = Path(diag.file_path).expanduser().resolve()
                relative = diag_path.relative_to(root_path).as_posix().lower()
                relative_paths.add(relative)
            except Exception:
                continue

        return relative_paths
