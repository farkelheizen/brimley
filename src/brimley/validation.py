from typing import Dict, Any, Type, Optional
from pydantic import create_model, Field, ValidationError
from brimley.schemas import ToolDefinition, Argument

# Map string types from JSON to Python types
TYPE_MAPPING = {
    "string": str,
    "int": int,
    "float": float,
    "bool": bool
}

def validate_tool_arguments(tool_def: ToolDefinition, raw_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dynamically validates user arguments against a ToolDefinition.

    Args:
        tool_def: The Pydantic model representing the tool schema.
        raw_args: A dictionary of arguments provided by the caller (LLM/User).

    Returns:
        A dictionary of validated, casted arguments.

    Raises:
        ValidationError: If arguments do not match the schema.
        ValueError: If an unknown type is encountered in schema.
    """
    field_definitions = {}

    for arg in tool_def.arguments.inline:
        python_type = TYPE_MAPPING.get(arg.type)
        if not python_type:
            # Fallback or error? For MVP, error is safer.
            raise ValueError(f"Unknown argument type '{arg.type}' in tool '{tool_def.tool_name}'")

        if arg.required:
            # In Pydantic, (Type, ...) means required field
            field_definitions[arg.name] = (python_type, ...)
        else:
            # Optional field with default
            # We wrap in Optional to be safe, though Pydantic handles strictly typed defaults well if they match.
            field_definitions[arg.name] = (Optional[python_type], arg.default)

    # Note: `entity_ref` logic would go here in future phases.

    # Create the dynamic Pydantic model
    # We use the tool name in the model name for clearer error messages
    DynamicModel = create_model(f"{tool_def.tool_name}_Args", **field_definitions)

    # Validate
    model_instance = DynamicModel(**raw_args)

    return model_instance.model_dump()
