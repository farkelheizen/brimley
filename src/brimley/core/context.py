from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr
from brimley.core.entity import Entity, ContentBlock, PromptMessage
from brimley.core.registry import Registry
from brimley.core.models import BrimleyFunction, FrameworkSettings, AppConfig, MCPSettings, AutoReloadSettings
from brimley.utils.diagnostics import BrimleyDiagnostic


class RuntimeErrorRecord(BaseModel):
    """Represents one persisted runtime diagnostic entry for `/errors` output."""

    key: str
    object_name: str
    error_class: str
    severity: str
    message: str
    file_path: str
    line_number: Optional[int] = None
    source: str
    status: str = "active"
    first_seen_index: int
    last_seen_index: int
    resolved_at_index: Optional[int] = None

class BrimleyContext(Entity):
    """
    The central execution context injected into every function.
    """
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    
    # Framework Settings (Maps to 'brimley' section)
    settings: FrameworkSettings = Field(default_factory=FrameworkSettings)
    
    # Application Config (Maps to 'config' section)
    config: AppConfig = Field(default_factory=AppConfig)

    # MCP Runtime Settings (Maps to 'mcp' section)
    mcp: MCPSettings = Field(default_factory=MCPSettings)

    # Auto Reload Runtime Settings (Maps to top-level 'auto_reload' section)
    auto_reload: AutoReloadSettings = Field(default_factory=AutoReloadSettings)
    
    # Application State: Mutable storage for request/session data
    app: Dict[str, Any] = Field(default_factory=dict)
    
    # Function Registry: Lookup for available functions
    functions: Registry[BrimleyFunction] = Field(default_factory=Registry)
    
    # Entity Registry: Lookup for domain models and data schemas
    entities: Registry[Entity] = Field(default_factory=Registry)
    
    # Database Definitions (Maps to 'databases' section)
    databases: Dict[str, Any] = Field(default_factory=dict)

    # Runtime Error Set: Active unresolved diagnostics surfaced by REPL `/errors`
    runtime_errors_active: Dict[str, RuntimeErrorRecord] = Field(default_factory=dict)

    # Runtime Error History: Recently resolved diagnostics kept for bounded history queries
    runtime_errors_history: List[RuntimeErrorRecord] = Field(default_factory=list)

    # Runtime Error History Capacity
    runtime_error_history_limit: int = Field(default=200)

    _runtime_error_sequence: int = PrivateAttr(default=0)

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None, **data: Any):
        """
        Initialize the context, optionally with a configuration dictionary.
        """
        if config_dict:
            # Seed fields from config_dict if not explicitly provided in data
            if 'settings' not in data:
                data['settings'] = FrameworkSettings(**config_dict.get('brimley', {}))
            if 'config' not in data:
                data['config'] = AppConfig(**config_dict.get('config', {}))
            if 'mcp' not in data:
                data['mcp'] = MCPSettings(**config_dict.get('mcp', {}))
            if 'auto_reload' not in data:
                data['auto_reload'] = AutoReloadSettings(**config_dict.get('auto_reload', {}))
            if 'app' not in data:
                data['app'] = config_dict.get('state', {})
            if 'databases' not in data:
                data['databases'] = config_dict.get('databases', {})
        
        super().__init__(**data)

    def model_post_init(self, __context: Any) -> None:
        """
        Initialize the context, registering built-in entities.
        """
        # Register built-in entities
        # Note: We are registering the classes themselves as they have name attributes
        # and represent the definition of the entity.
        if "ContentBlock" not in self.entities:
            # We ensure they have a name for the registry
            ContentBlock.name = "ContentBlock"
            self.entities.register(ContentBlock) # type: ignore
            
        if "PromptMessage" not in self.entities:
            PromptMessage.name = "PromptMessage"
            self.entities.register(PromptMessage) # type: ignore

    def execute_function_by_name(
        self,
        function_name: str,
        input_data: Dict[str, Any],
        runtime_injections: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a registered function by name using the standard runtime pipeline."""
        from brimley.execution.execute_helper import execute_function_by_name

        return execute_function_by_name(
            context=self,
            function_name=function_name,
            input_data=input_data,
            runtime_injections=runtime_injections,
        )

    def sync_runtime_error_set(self, diagnostics: List[BrimleyDiagnostic], source: str) -> None:
        """Synchronize the persisted runtime error set against the latest diagnostics list."""
        self._runtime_error_sequence += 1
        sequence = self._runtime_error_sequence
        next_active: Dict[str, RuntimeErrorRecord] = {}

        for diag in diagnostics:
            key = self._runtime_error_key(diag)
            if key in next_active:
                continue

            existing = self.runtime_errors_active.get(key)
            if existing is None:
                next_active[key] = RuntimeErrorRecord(
                    key=key,
                    object_name=self._diagnostic_object_name(diag),
                    error_class=diag.error_code,
                    severity=diag.severity,
                    message=diag.message,
                    file_path=diag.file_path,
                    line_number=diag.line_number,
                    source=source,
                    status="active",
                    first_seen_index=sequence,
                    last_seen_index=sequence,
                )
                continue

            next_active[key] = existing.model_copy(
                update={
                    "severity": diag.severity,
                    "message": diag.message,
                    "line_number": diag.line_number,
                    "source": source,
                    "status": "active",
                    "last_seen_index": sequence,
                    "resolved_at_index": None,
                }
            )

        for key, existing in self.runtime_errors_active.items():
            if key in next_active:
                continue

            resolved_record = existing.model_copy(
                update={
                    "status": "resolved",
                    "resolved_at_index": sequence,
                }
            )
            self.runtime_errors_history.append(resolved_record)

        if len(self.runtime_errors_history) > self.runtime_error_history_limit:
            self.runtime_errors_history = self.runtime_errors_history[-self.runtime_error_history_limit :]

        self.runtime_errors_active = next_active

    def get_runtime_errors(
        self,
        include_resolved: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RuntimeErrorRecord], int]:
        """Return sorted, paginated runtime errors for REPL `/errors` output."""
        safe_limit = max(1, limit)
        safe_offset = max(0, offset)

        records: List[RuntimeErrorRecord] = list(self.runtime_errors_active.values())
        if include_resolved:
            records.extend(self.runtime_errors_history)

        ordered_records = sorted(
            records,
            key=lambda record: (
                self._severity_rank(record.severity),
                record.last_seen_index,
            ),
            reverse=True,
        )

        total = len(ordered_records)
        page = ordered_records[safe_offset : safe_offset + safe_limit]
        return page, total

    def _runtime_error_key(self, diagnostic: BrimleyDiagnostic) -> str:
        line_number = "" if diagnostic.line_number is None else str(diagnostic.line_number)
        return "|".join(
            [
                diagnostic.file_path,
                diagnostic.error_code,
                diagnostic.message,
                line_number,
                diagnostic.severity,
            ]
        )

    def _diagnostic_object_name(self, diagnostic: BrimleyDiagnostic) -> str:
        file_name = Path(diagnostic.file_path).name
        stem = Path(file_name).stem
        return stem or "unknown"

    def _severity_rank(self, severity: str) -> int:
        ranks = {
            "critical": 3,
            "error": 2,
            "warning": 1,
            "info": 0,
        }
        return ranks.get(severity.lower(), 0)
