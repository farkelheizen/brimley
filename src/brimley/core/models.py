from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import Field
from brimley.core.entity import Entity, PromptMessage

class BrimleyFunction(Entity):
    """
    Abstract base class for all function types in Brimley.
    """
    name: str = Field(..., pattern=r'^[a-zA-Z0-9_]+$')
    type: str
    description: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
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
