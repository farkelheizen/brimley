from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field
from brimley.core.models import BrimleyFunction, normalize_type_expression
from brimley.core.context import BrimleyContext

class ArgumentDef(BaseModel):
    name: str
    type: str # 'string', 'int', 'bool', etc.
    required: bool = True
    default: Any = None
    from_context: Optional[str] = None

class ArgumentResolver:
    """
    Handles parsing, merging, and validation of function arguments.
    """

    @classmethod
    def resolve(
        cls, 
        func: BrimleyFunction, 
        user_input: Dict[str, Any], 
        context: BrimleyContext
    ) -> Dict[str, Any]:
        
        if not func.arguments:
            return {}

        defs = cls._parse_definitions(func.arguments)
        resolved = {}

        for arg_def in defs:
            value = None
            
            # 1. Context Injection (Priority 1)
            if arg_def.from_context:
                value = cls._get_context_value(context, arg_def.from_context)
            
            # 2. User Input (Priority 2)
            elif arg_def.name in user_input:
                value = user_input[arg_def.name]
            
            # 3. Defaults (Priority 3)
            elif arg_def.default is not None:
                value = arg_def.default
            
            # 4. Validation
            if value is None and arg_def.required:
                raise ValueError(f"Missing required argument: '{arg_def.name}'")
            
            if value is not None:
                # Type casting/checking
                value = cls._cast_value(value, arg_def.type)
                
            resolved[arg_def.name] = value

        return resolved

    @classmethod
    def _parse_definitions(cls, arguments_blob: Dict[str, Any]) -> list[ArgumentDef]:
        """
        Parses the raw 'arguments' dict into normalized ArgumentDefs.
        Supports 'inline' mode (Shorthand, Complex).
        """
        defs = []
        
        # We focus on 'inline' for now as per specs
        inline = arguments_blob.get("inline", {})
        
        # Check if 'inline' is Shorthand/Complex or Standard Schema
        # Spec: "Complex Mode... values are dictionaries... top-level key does not contain properties"
        # Spec: "Standard Mode... contains properties key"
        
        if "properties" in inline:
            raise ValueError(
                "JSON Schema argument mode is not supported in v0.4 runtime authoring. "
                "Use constrained inline FieldSpec definitions instead."
            )
        else:
            # Iterate keys -> Shorthand or Complex
            for name, spec in inline.items():
                
                # A. Shorthand: "name": "int"
                if isinstance(spec, str):
                    try:
                        normalized_type = normalize_type_expression(spec)
                    except ValueError as e:
                        raise ValueError(f"Unsupported type expression for argument '{name}': {e}") from e

                    defs.append(ArgumentDef(
                        name=name,
                        type=normalized_type,
                        required=True # Shorthand implies required
                    ))
                
                # B. Complex: "name": {"type": "int", "default": 1}
                elif isinstance(spec, dict):
                    # Extract logic
                    arg_type = spec.get("type", "string")
                    try:
                        normalized_type = normalize_type_expression(str(arg_type))
                    except ValueError as e:
                        raise ValueError(f"Unsupported type expression for argument '{name}': {e}") from e

                    default = spec.get("default")
                    from_ctx = spec.get("from_context")
                    # It's required if no default and no context and not marked optional?
                    # Generally yes.
                    required = (default is None and from_ctx is None)
                    
                    defs.append(ArgumentDef(
                        name=name,
                        type=normalized_type,
                        required=required,
                        default=default,
                        from_context=from_ctx
                    ))
                    
        return defs

    @classmethod
    def _get_context_value(cls, context: BrimleyContext, path: str) -> Any:
        """
        Resolves dot-notation path (e.g. 'app.user.id') against attributes
        of BrimleyContext.
        """
        parts = path.split('.')
        current = context
        
        # Traverse
        # Context has .app, .config, .databases, etc.
        # But 'app' is a dict, 'config' is a Pydantic model.
        for i, part in enumerate(parts):
            # If current is BrimleyContext or Pydantic model, use getattr
            if hasattr(current, part):
                current = getattr(current, part)
            # If current is dict, use getitem
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Failure
                raise ValueError(f"Context path '{path}' not found (failed at '{part}').")
        
        return current

    @classmethod
    def _cast_value(cls, value: Any, type_name: str) -> Any:
        """
        Simple casting logic.
        """
        if type_name.endswith("[]"):
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"Expected a list for type '{type_name}'.")
            item_type = type_name[:-2]
            return [cls._cast_value(item, item_type) for item in value]

        if type_name == "int" or type_name == "integer":
            return int(value)
        elif type_name == "str" or type_name == "string":
            return str(value)
        elif type_name == "bool" or type_name == "boolean":
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        elif type_name == "float" or type_name == "number":
            return float(value)
        elif type_name == "decimal":
            return Decimal(value)
        elif type_name == "date":
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return date.fromisoformat(value)
            raise ValueError("Expected ISO date string for type 'date'.")
        elif type_name == "datetime":
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            raise ValueError("Expected ISO datetime string for type 'datetime'.")
        # primitive / any
        return value
