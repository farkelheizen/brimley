from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from brimley.core.entity import Entity, PromptMessage

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

class BrimleyFunction(Entity):
    """
    Abstract base class for all function types in Brimley.
    """
    name: str = Field(..., pattern=r'^[a-zA-Z0-9_]+$')
    type: str
    description: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    mcp: Optional[MCPConfig] = None
    return_shape: Union[str, Dict[str, Any]]

class PythonFunction(BrimleyFunction):
    """
    A function backed by native Python code.
    """
    type: Literal["python_function"]
    handler: Optional[str] = None  # e.g., "my_pkg.mod.func_name"

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
