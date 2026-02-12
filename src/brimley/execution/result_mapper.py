from typing import Any, Dict, List, Optional, Union, Type, get_args
import pydantic
from pydantic import TypeAdapter, ValidationError
from brimley.core.context import BrimleyContext
from brimley.core.models import BrimleyFunction
from brimley.core.entity import Entity

class ResultMapper:
    """
    Marshals raw function output into the structure defined by return_shape.
    """

    PRIMITIVE_MAP = {
        "string": str,
        "int": int,
        "float": float,
        "bool": bool,
        "void": type(None),
        "decimal": float, # For now mapping decimal to float
        "dict": dict,
        "list": list,
        "any": Any,
    }

    @classmethod
    def map_result(cls, raw_data: Any, func: BrimleyFunction, context: BrimleyContext) -> Any:
        shape = func.return_shape
        
        if not shape or shape == "void":
            return None

        if isinstance(shape, str):
            return cls._map_by_shorthand(raw_data, shape, context)
        
        if isinstance(shape, dict):
            return cls._map_by_structured_shape(raw_data, shape, context)
        
        return raw_data

    @classmethod
    def _map_by_shorthand(cls, data: Any, shape_str: str, context: BrimleyContext) -> Any:
        # Handle complex list[dict] or List[Any] style strings by converting to [] syntax
        if "[" in shape_str and not shape_str.endswith("[]"):
            # Very naive conversion of "list[something]" to "something[]"
            import re
            match = re.match(r"list\[(.*)\]", shape_str, re.IGNORECASE)
            if match:
                shape_str = f"{match.group(1)}[]"

        is_list = False
        base_type_str = shape_str
        
        if shape_str.endswith("[]"):
            is_list = True
            base_type_str = shape_str[:-2]

        # Handle list wrapping if we got a single item but expected a list
        if is_list and not isinstance(data, (list, tuple)):
            data = [data]
        # Handle unwrapping if we got a list and expected single item
        elif not is_list and isinstance(data, (list, tuple)):
            if len(data) == 0:
                return None
            if len(data) > 1:
                raise ValueError(f"Expected single row for return shape '{shape_str}', but got {len(data)} rows.")
            data = data[0]

        target_type = cls._resolve_type(base_type_str, context)
        
        # Explicit coercion for primitives if Pydantic is too strict
        if not is_list:
            if target_type is str and data is not None:
                data = str(data)
            elif target_type is int and isinstance(data, str):
                try: data = int(data)
                except: pass
            elif target_type is float and isinstance(data, str):
                try: data = float(data)
                except: pass

        if is_list:
            adapter = TypeAdapter(List[target_type]) # type: ignore
        else:
            adapter = TypeAdapter(target_type)

        try:
            return adapter.validate_python(data)
        except ValidationError as e:
            # We could wrap this in a custom Brimley error later
            raise e

    @classmethod
    def _map_by_structured_shape(cls, data: Any, shape_dict: Dict[str, Any], context: BrimleyContext) -> Any:
        # Structured shapes can have 'entity_ref' or 'inline'
        if "entity_ref" in shape_dict:
            return cls._map_by_shorthand(data, shape_dict["entity_ref"], context)
        
        if "inline" in shape_dict:
            inline_spec = shape_dict["inline"]
            # Design doc trigger: if values are strings, it's shorthand
            # If values are dicts, it's complex metadata.
            
            # For simplicity, let's create a dynamic Pydantic model for validation
            fields = {}
            for field_name, field_def in inline_spec.items():
                if isinstance(field_def, str):
                    field_type = cls._resolve_type(field_def, context)
                    fields[field_name] = (field_type, ...)
                elif isinstance(field_def, dict):
                    type_str = field_def.get("type", "string")
                    field_type = cls._resolve_type(type_str, context)
                    fields[field_name] = (field_type, ...)
            
            DynamicModel = pydantic.create_model("InlineResult", **fields)
            
            if isinstance(data, (list, tuple)):
                # If we have a list of rows for an inline shape, we probably should return a list of models
                # But typically inline shapes without [] suffix are single objects.
                # If return_shape itself doesn't support [] for structured dicts in spec yet,
                # we'll assume single object unless we see otherwise.
                if len(data) == 0: return None
                data = data[0]
            
            return DynamicModel(**data).model_dump()

        return data

    @classmethod
    def _resolve_type(cls, type_name: str, context: BrimleyContext) -> Type:
        # Lowercase for case-insensitivity in shorthand strings
        tn = type_name.lower()

        # 1. Check Primitives
        if tn in cls.PRIMITIVE_MAP:
            return cls.PRIMITIVE_MAP[tn]
        
        # 2. Check Entities (Keep original casing for entities)
        entity_class = context.entities.get(type_name)
        if entity_class:
            return entity_class
        
        # 3. Handle Python built-ins like list[dict] where user might use literal python typing
        # If it contains '[', it's handled by _map_by_shorthand usually, 
        # but if the user passed 'list' or 'dict' it should map to the primitives.
        
        # 4. Default to Any or raise? Let's raise for clarity in this engine.
        raise ValueError(f"Unknown return type or entity: '{type_name}'")
