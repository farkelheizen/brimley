import pytest
from pydantic import ValidationError
from brimley.schemas import ToolDefinition, ToolType, ReturnType, ArgumentsBlock, Argument, Implementation, ReturnShape
from brimley.validation import validate_tool_arguments

@pytest.fixture
def sample_tool_def():
    """Creates a sample tool definition for testing validation."""
    return ToolDefinition(
        tool_name="test_tool",
        tool_type=ToolType.LOCAL_SQL,
        description="Test tool",
        implementation=Implementation(sql_template=["SELECT 1"]),
        return_shape=ReturnShape(type=ReturnType.VALUE),
        arguments=ArgumentsBlock(
            inline=[
                Argument(name="id", type="int", required=True),
                Argument(name="name", type="string", required=False, default="Guest"),
                Argument(name="is_active", type="bool", required=True),
                Argument(name="score", type="float", required=False)
            ]
        )
    )

def test_validate_runtime_args_success(sample_tool_def):
    """Pass correct dictionary to validator and expect clean dict back."""
    raw_args = {
        "id": 123,
        "is_active": True,
        "name": "Alice",
        "score": 99.5
    }
    validated = validate_tool_arguments(sample_tool_def, raw_args)
    
    assert validated["id"] == 123
    assert validated["name"] == "Alice"
    assert validated["is_active"] is True
    assert validated["score"] == 99.5

def test_validate_runtime_args_defaults(sample_tool_def):
    """Ensure defaults are applied."""
    raw_args = {
        "id": 456,
        "is_active": False
    }
    validated = validate_tool_arguments(sample_tool_def, raw_args)
    
    assert validated["id"] == 456
    assert validated["name"] == "Guest"  # Default applied
    assert validated["is_active"] is False
    assert validated["score"] is None

def test_validate_runtime_args_type_casting(sample_tool_def):
    """Pydantic should handle basic casting (e.g. "123" -> 123)."""
    raw_args = {
        "id": "789",
        "is_active": "true" 
    }
    validated = validate_tool_arguments(sample_tool_def, raw_args)
    assert validated["id"] == 789
    assert validated["is_active"] is True

def test_validate_runtime_args_failure_missing(sample_tool_def):
    """Missing required arg should raise ValidationError."""
    raw_args = {"name": "Bob"} # 'id' and 'is_active' missing
    with pytest.raises(ValidationError) as excinfo:
        validate_tool_arguments(sample_tool_def, raw_args)
    
    errors = excinfo.value.errors()
    failed_fields = [e["loc"][0] for e in errors]
    assert "id" in failed_fields
    assert "is_active" in failed_fields

def test_validate_runtime_args_failure_type(sample_tool_def):
    """Wrong type should raise ValidationError."""
    raw_args = {
        "id": "not_an_int",
        "is_active": True
    }
    with pytest.raises(ValidationError):
        validate_tool_arguments(sample_tool_def, raw_args)
