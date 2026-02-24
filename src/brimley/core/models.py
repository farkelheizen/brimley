import re
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from brimley.core.entity import Entity as BaseEntity, PromptMessage


_GENERIC_LIST_PATTERN = re.compile(r"^(?:typing\.)?(?:list|List)\[(.+)\]$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


class MCPConfig(BaseModel):
    """
    MCP metadata for exposing a Brimley function as an MCP tool.
    """
    model_config = ConfigDict(extra='forbid')

    type: Literal["tool"]
    description: Optional[str] = None

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
    return_shape: Union[str, Dict[str, Any]]

class PythonFunction(BrimleyFunction):
    """
    A function backed by native Python code.
    """
    type: Literal["python_function"]
    reload: bool = True
    handler: Optional[str] = None  # e.g., "my_pkg.mod.func_name"


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
