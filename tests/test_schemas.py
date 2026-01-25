import pytest
from pydantic import ValidationError
from brimley.schemas import ToolDefinition, ToolType, ReturnType

def test_parse_valid_tool_def():
    """Ensure a valid dictionary parses into a ToolDefinition model."""
    data = {
        "tool_name": "promote_customer",
        "tool_type": "LOCAL_SQL",
        "description": "Promotes a customer to VIP status.",
        "action": "UPDATE",
        "implementation": {
            "sql_template": [
                "UPDATE customers",
                "SET tier = 'VIP'",
                "WHERE id = :id"
            ]
        },
        "return_shape": {
            "type": "VOID"
        },
        "arguments": {
            "inline": [
                {
                    "name": "id",
                    "type": "int",
                    "required": True
                }
            ]
        }
    }
    
    tool = ToolDefinition(**data)
    
    assert tool.tool_name == "promote_customer"
    assert tool.tool_type == ToolType.LOCAL_SQL
    assert tool.return_shape.type == ReturnType.VOID
    assert len(tool.arguments.inline) == 1
    assert tool.arguments.inline[0].name == "id"
    assert tool.implementation.sql_template == [
        "UPDATE customers", 
        "SET tier = 'VIP'", 
        "WHERE id = :id"
    ]

def test_invalid_tool_type():
    """Ensure invalid tool_type raises a validation error."""
    data = {
        "tool_name": "bad_tool",
        "tool_type": "INVALID_TYPE",
        "description": "This should fail.",
        "implementation": {},
        "return_shape": {"type": "VOID"},
        "arguments": {"inline": []}
    }
    with pytest.raises(ValidationError):
        ToolDefinition(**data)
