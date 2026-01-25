from typing import List, Optional, Any, Union, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class ToolType(str, Enum):
    LOCAL_SQL = "LOCAL_SQL"
    PROMPT_BUILDER = "PROMPT_BUILDER"

class ReturnType(str, Enum):
    TABLE = "TABLE"
    RECORD = "RECORD"
    VALUE = "VALUE"
    LIST = "LIST"
    VOID = "VOID"

class Argument(BaseModel):
    name: str
    type: str # keeping as string "int", "string" etc. for now, will validate later
    required: bool = True
    default: Optional[Any] = None

class ArgumentsBlock(BaseModel):
    entity_ref: Optional[str] = None
    inline: List[Argument] = Field(default_factory=list)

class Implementation(BaseModel):
    sql_template: Optional[List[str]] = None
    # For PROMPT_BUILDER later:
    template_files: Optional[List[str]] = None
    engine: str = "jinja2"
    output_format: str = "STRING"

class ReturnShape(BaseModel):
    type: ReturnType

class ToolDefinition(BaseModel):
    tool_name: str
    tool_type: ToolType
    description: str
    action: Optional[str] = None
    implementation: Implementation
    return_shape: ReturnShape
    arguments: ArgumentsBlock

    @field_validator('tool_type', mode='before')
    @classmethod
    def validate_tool_type_str(cls, v):
        # Allow case-insensitive matching if needed, but spec implies exact matches.
        # Strict validation is handled by Enum.
        return v
