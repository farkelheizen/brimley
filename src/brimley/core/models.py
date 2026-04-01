import re
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from brimley.core.entity import Entity as BaseEntity, PromptMessage


_GENERIC_LIST_PATTERN = re.compile(r"^(?:typing\.)?(?:list|List)\[(.+)\]$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VALID_LOG_LEVELS = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}


def _normalize_log_level(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in _VALID_LOG_LEVELS:
        valid = ", ".join(sorted(_VALID_LOG_LEVELS))
        raise ValueError(f"Invalid log level '{value}'. Expected one of: {valid}.")
    return normalized


def normalize_type_expression(
    type_expr: str,
    *,
    allow_void: bool = False,
    allow_legacy_containers: bool = False,
) -> str:
    """Normalize and validate a constrained Brimley type expression."""
    normalized = type_expr.strip()
    if not normalized:
        raise ValueError("Type expression cannot be empty.")

    lowered = normalized.lower()
    if "|" in normalized or lowered.startswith("optional[") or lowered.startswith("union["):
        raise ValueError(f"Union types are not supported in v0.4: '{type_expr}'")

    list_match = _GENERIC_LIST_PATTERN.fullmatch(normalized)
    if list_match:
        inner = normalize_type_expression(
            list_match.group(1).strip(),
            allow_void=False,
            allow_legacy_containers=allow_legacy_containers,
        )
        if inner.endswith("[]"):
            raise ValueError(f"Only one-dimensional lists are supported in v0.4: '{type_expr}'")
        return f"{inner}[]"

    if normalized.endswith("[]"):
        inner = normalize_type_expression(
            normalized[:-2].strip(),
            allow_void=False,
            allow_legacy_containers=allow_legacy_containers,
        )
        if inner.endswith("[]"):
            raise ValueError(f"Only one-dimensional lists are supported in v0.4: '{type_expr}'")
        return f"{inner}[]"

    canonical: dict[str, str] = {
        "str": "string",
        "string": "string",
        "int": "int",
        "integer": "int",
        "float": "float",
        "number": "float",
        "bool": "bool",
        "boolean": "bool",
        "decimal": "decimal",
        "date": "date",
        "datetime": "datetime",
        "primitive": "primitive",
        "any": "primitive",
    }

    if allow_void and lowered in {"void", "none", "nonetype"}:
        return "void"

    if lowered in canonical:
        return canonical[lowered]

    if lowered in {"dict", "object", "list", "array", "set", "tuple"}:
        if allow_legacy_containers:
            if lowered in {"dict", "object"}:
                return "dict"
            if lowered in {"list", "array", "set", "tuple"}:
                return "list"
        raise ValueError(
            f"Unsupported open container type '{type_expr}'. Use primitives/entities and one-dimensional lists only."
        )

    if "[" in normalized or "]" in normalized:
        raise ValueError(f"Unsupported generic type expression in v0.4: '{type_expr}'")

    entity_candidate = normalized.rsplit(".", 1)[-1]
    if not _IDENTIFIER_PATTERN.fullmatch(entity_candidate):
        raise ValueError(f"Unsupported type expression in v0.4: '{type_expr}'")

    return entity_candidate

class FrameworkSettings(BaseSettings):
    """
    Framework-level settings (the 'brimley' section in brimley.yaml).
    """
    model_config = SettingsConfigDict(env_prefix='BRIMLEY_', extra='ignore')
    
    env: str = "development"
    app_name: str = "Brimley App"
    log_level: str = "INFO"
    logging: "LoggingSettings" = Field(default_factory=lambda: LoggingSettings())

    @model_validator(mode="before")
    @classmethod
    def _apply_legacy_log_level(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        logging_section = data.get("logging")
        legacy_level = data.get("log_level")

        if logging_section is None and legacy_level is not None:
            data["logging"] = {"level": legacy_level}
            return data

        if isinstance(logging_section, dict) and "level" not in logging_section and legacy_level is not None:
            logging_section["level"] = legacy_level

        return data

    @field_validator("log_level")
    @classmethod
    def _validate_legacy_log_level(cls, value: str) -> str:
        return _normalize_log_level(value)


class LoggingFileSettings(BaseModel):
    """Optional file sink settings under brimley.logging.file."""

    model_config = ConfigDict(extra='ignore')

    path: Optional[str] = None
    level: str = "DEBUG"
    format: Literal["text", "jsonl"] = "text"
    rotation: Optional[str] = None
    retention: Optional[str] = None

    @field_validator("level")
    @classmethod
    def _validate_level(cls, value: str) -> str:
        return _normalize_log_level(value)


class LoggingSettings(BaseModel):
    """Logging settings under brimley.logging."""

    model_config = ConfigDict(extra='ignore')

    level: str = "INFO"
    modules: Dict[str, str] = Field(default_factory=dict)
    file: LoggingFileSettings = Field(default_factory=LoggingFileSettings)
    managed: bool = True

    @field_validator("level")
    @classmethod
    def _validate_level(cls, value: str) -> str:
        return _normalize_log_level(value)

    @field_validator("modules")
    @classmethod
    def _validate_modules(cls, value: Dict[str, str]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for module_name, level in value.items():
            key = module_name.strip()
            if not key:
                raise ValueError("Logging module names cannot be empty.")
            normalized[key] = _normalize_log_level(level)
        return normalized


FrameworkSettings.model_rebuild()

class AppConfig(BaseModel):
    """
    User-defined application configuration (the 'config' section in brimley.yaml).
    """
    model_config = ConfigDict(extra='allow')


class MCPSettings(BaseModel):
    """
    Runtime MCP settings (the 'mcp' section in brimley.yaml).
    """
    model_config = ConfigDict(extra='ignore')

    embedded: bool = True
    transport: Literal["sse", "stdio"] = "sse"
    host: str = "127.0.0.1"
    port: int = 8000


class AutoReloadSettings(BaseModel):
    """
    Runtime auto-reload settings (the top-level 'auto_reload' section in brimley.yaml).
    """
    model_config = ConfigDict(extra='ignore')

    enabled: bool = False
    interval_ms: int = Field(default=1000, ge=100)
    debounce_ms: int = Field(default=300, ge=0)
    include_patterns: List[str] = Field(default_factory=lambda: ["*.py", "*.sql", "*.md", "*.yaml"])
    exclude_patterns: List[str] = Field(default_factory=list)


class ExecutionQueueSettings(BaseModel):
    """Queue configuration for bounded synchronous execution dispatch."""

    model_config = ConfigDict(extra='ignore')

    max_size: int = Field(default=128, ge=0)
    on_full: Literal["reject", "block"] = "reject"


class ExecutionSettings(BaseModel):
    """Global execution runtime settings (the `execution` section in brimley.yaml)."""

    model_config = ConfigDict(extra='ignore')

    thread_pool_size: int = Field(default=8, ge=1)
    timeout_seconds: float = Field(default=30.0, gt=0)
    queue: ExecutionQueueSettings = Field(default_factory=ExecutionQueueSettings)


class MCPConfig(BaseModel):
    """
    MCP metadata for exposing a Brimley function as an MCP tool.
    """
    model_config = ConfigDict(extra='forbid')

    type: Literal["tool"]
    description: Optional[str] = None


class TaskConfig(BaseModel):
    """
    Scheduling metadata for a Brimley managed task function.

    Applied via ``@function(task={...})``. Introduced in Brimley v0.9.

    Attributes:
        interval: Human-readable execution interval (e.g. ``"5m"``, ``"30s"``).
            Must be >= 1 second. Parsed by :func:`~brimley.utils.time_parser.parse_duration`.
        immediate: If True, the first iteration runs immediately at startup
            instead of waiting for the first interval.
        retries: Maximum retry attempts on failure. None = unlimited.
        retry_interval: Retry backoff spec (e.g. ``"10s exponential"``).
            Parsed by :func:`~brimley.utils.time_parser.parse_retry_interval`.
    """

    model_config = ConfigDict(extra="forbid")

    interval: str = Field(..., min_length=1)
    immediate: bool = False
    retries: Optional[int] = Field(default=None, ge=0)
    retry_interval: str = "1s exponential"


class BrimleyFunction(BaseEntity):
    """
    Abstract base class for all function types in Brimley.
    """
    name: str = Field(..., pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')
    type: str
    description: Optional[str] = None
    canonical_id: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    mcp: Optional[MCPConfig] = None
    timeout_seconds: Optional[float] = Field(default=None, gt=0)
    return_shape: Union[str, Dict[str, Any]]
    task: Optional["TaskConfig"] = None  # populated by Scanner for task functions (v0.9)

class PythonFunction(BrimleyFunction):
    """
    A function backed by native Python code.
    """
    type: Literal["python_function"]
    reload: bool = True
    handler: Optional[str] = None  # e.g., "my_pkg.mod.func_name"
    is_async: bool = False  # set by python_parser; True for async def functions


class DiscoveredEntity(BaseEntity):
    """A discovered entity definition from YAML or Python sources."""

    type: Literal["entity", "python_entity"] = "entity"
    canonical_id: Optional[str] = None
    handler: Optional[str] = None
    raw_definition: Optional[Dict[str, Any]] = None

class SqlFunction(BrimleyFunction):
    """
    A function backed by a SQL query.
    """
    type: Literal["sql_function"]
    connection: str = "default"
    sql_body: str

class TemplateFunction(BrimleyFunction):
    """
    A function backed by a template (Markdown/Jinja).
    """
    type: Literal["template_function"]
    template_engine: str = "jinja2"
    template_body: Optional[str] = None
    messages: Optional[List[PromptMessage]] = None


# ---------------------------------------------------------------------------
# Brimley 0.7: secrets: block (ADR-0003)
# ---------------------------------------------------------------------------

class SecretSource(BaseModel):
    """
    A single resolution source entry for a named secret.

    Exactly one of ``env`` or ``provider`` must be specified per entry.
    Provider sources are structurally recognised in v0.7 but raise
    ``BrimleySecretResolutionError`` at scanner load time until DI (v0.8).
    """

    model_config = ConfigDict(extra="forbid")

    env: Optional[str] = None
    provider: Optional[str] = None

    @model_validator(mode="after")
    def _validate_exactly_one_source(self) -> "SecretSource":
        provided = sum([
            self.env is not None,
            self.provider is not None,
        ])
        if provided != 1:
            raise ValueError(
                "Each secret source entry must specify exactly one of: 'env', 'provider'."
            )
        return self


# ---------------------------------------------------------------------------
# Brimley 0.7: API Functions (.yaml, type=api_function)
# ---------------------------------------------------------------------------

class ApiRequestConfig(BaseModel):
    """HTTP request configuration block for an api_function."""

    model_config = ConfigDict(extra="allow")

    method: str = "GET"
    url: str
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    timeout: float = Field(default=30.0, gt=0)


class ApiResponseHandler(BaseModel):
    """Response handling configuration for a single HTTP status code."""

    model_config = ConfigDict(extra="allow")

    type: Optional[str] = None
    parse: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ResultMapping(BaseModel):
    """
    Per-code result handling entry for ``results:`` block (API and CLI functions).

    Keys in the parent ``results:`` dict map HTTP status codes or CLI exit codes
    to this model.  Supported code key formats:

    - **API functions:** 3-digit numeric string (``"200"``), wildcard (``"2xx"``),
      or ``"default"`` catch-all.
    - **CLI functions:** numeric string (``"0"``–``"255"``) or ``"default"`` catch-all.

    The first key that matches wins (ordered first-match semantics per SD-3).

    Introduced in Brimley 0.7.
    """

    model_config = ConfigDict(extra="allow")

    type: str = "text"
    parse: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    empty: Optional[bool] = None


class ApiFunction(BrimleyFunction):
    """
    A function backed by an HTTP API call (httpx, async).

    Introduced in Brimley 0.7.
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["api_function"]
    request: ApiRequestConfig
    response: Optional[Dict[Any, Any]] = None
    results: Optional[Dict[str, ResultMapping]] = None
    secrets: Optional[Dict[str, List[SecretSource]]] = None


# ---------------------------------------------------------------------------
# Brimley 0.7: CLI Functions (.yaml, type=cli_function)
# ---------------------------------------------------------------------------

class CliParsingConfig(BaseModel):
    """Output parsing configuration for a cli_function (legacy ``parsing:`` block)."""

    model_config = ConfigDict(extra="allow")

    strategy: Literal["regex", "json", "text"] = "text"
    pattern: Optional[str] = None
    capture_group: Optional[str] = None


class CliFunction(BrimleyFunction):
    """
    A function backed by a shell CLI command (asyncio.create_subprocess_exec).

    Security constraints (non-negotiable per ADR-0002 / 0.7 spec):
    - shell=False always; command_arguments are a list.
    - timeout_seconds is required at scanner load time.
    - cwd defaults to project root, never inherited.
    - Only explicitly declared env: keys are passed to the subprocess when env is set.

    Introduced in Brimley 0.7.
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["cli_function"]
    command: str
    command_arguments: List[str] = Field(default_factory=list)
    timeout_seconds: float = Field(..., gt=0)
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    parsing: Optional[CliParsingConfig] = None
    results: Optional[Dict[str, ResultMapping]] = None
    secrets: Optional[Dict[str, List[SecretSource]]] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_command_arguments(cls, data: Any) -> Any:
        """Accept ``args`` as a backward-compatible alias for ``command_arguments``."""
        if isinstance(data, dict):
            if "args" in data and "command_arguments" not in data:
                data = dict(data)
                data["command_arguments"] = data.pop("args")
        return data

    @property
    def args(self) -> List[str]:
        """Backward-compatible alias for ``command_arguments``."""
        return self.command_arguments


# ---------------------------------------------------------------------------
# Brimley 0.8: DI — provider and lifecycle hook metadata
# ---------------------------------------------------------------------------

class ProviderMetadata(BaseModel):
    """
    Metadata describing a ``@provider``-decorated callable discovered during
    the AST scan phase.

    Introduced in Brimley 0.8.
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    scope: Literal["singleton", "request"] = "singleton"
    eager: bool = False
    module_path: str
    func_name: str
    handler: Optional[str] = None


class LifecycleHookMetadata(BaseModel):
    """
    Metadata describing an ``@on_startup`` or ``@on_shutdown``-decorated
    callable discovered during the AST scan phase.

    Introduced in Brimley 0.8.
    """

    model_config = ConfigDict(extra="forbid")

    hook_type: Literal["on_startup", "on_shutdown"]
    module_path: str
    func_name: str
    handler: Optional[str] = None
