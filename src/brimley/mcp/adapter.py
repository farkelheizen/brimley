from typing import Any, Dict, Tuple, Type

from pydantic import BaseModel, Field, create_model

from brimley.core.context import BrimleyContext
from brimley.core.models import BrimleyFunction
from brimley.core.registry import Registry
from brimley.execution.arguments import ArgumentResolver
from brimley.execution.dispatcher import Dispatcher


class BrimleyMCPAdapter:
    """
    Adapter scaffold for exposing Brimley functions through MCP.
    """

    def __init__(self, registry: Registry[BrimleyFunction], context: BrimleyContext):
        """
        Initialize the adapter with function registry and runtime context.
        """
        self.registry = registry
        self.context = context
        self.dispatcher = Dispatcher()

    def discover_tools(self) -> list[BrimleyFunction]:
        """
        Return only functions explicitly marked for MCP exposure.
        """
        return [
            func
            for func in self.registry
            if getattr(func, "mcp", None) is not None and func.mcp.type == "tool"
        ]

    def build_tool_input_model(self, func: BrimleyFunction) -> Type[BaseModel]:
        """
        Build a Pydantic input model for a tool, excluding from_context arguments.
        """
        inline_arguments = (func.arguments or {}).get("inline", {})
        field_definitions: Dict[str, Tuple[Any, Any]] = {}

        for arg_name, arg_spec in inline_arguments.items():
            if isinstance(arg_spec, str):
                field_definitions[arg_name] = (self._map_type(arg_spec), ...)
                continue

            if not isinstance(arg_spec, dict):
                continue

            if arg_spec.get("from_context"):
                continue

            arg_type = self._map_type(arg_spec.get("type", "string"))
            description = arg_spec.get("description")

            if "default" in arg_spec:
                default_value = arg_spec.get("default")
            else:
                default_value = ...

            if description:
                default_value = Field(default_value, description=description)

            field_definitions[arg_name] = (arg_type, default_value)

        model_name = f"{func.name.title().replace('_', '')}MCPInput"
        return create_model(model_name, **field_definitions)

    def _map_type(self, type_name: str) -> type[Any]:
        """
        Map Brimley argument type names to Python types.
        """
        normalized = type_name.lower()
        mapping: Dict[str, type[Any]] = {
            "string": str,
            "str": str,
            "int": int,
            "integer": int,
            "float": float,
            "number": float,
            "bool": bool,
            "boolean": bool,
            "dict": dict,
            "object": dict,
            "list": list,
            "array": list,
            "any": Any,
        }
        return mapping.get(normalized, Any)

    def create_tool_wrapper(self, func: BrimleyFunction):
        """
        Create a callable wrapper that resolves args and dispatches execution.
        """

        def wrapper(**tool_args: Any) -> Any:
            return self.execute_tool(func, tool_args)

        wrapper.__name__ = func.name
        wrapper.__doc__ = (func.mcp.description if getattr(func, "mcp", None) and func.mcp.description else func.description) or ""
        return wrapper

    def execute_tool(self, func: BrimleyFunction, tool_args: Dict[str, Any]) -> Any:
        """
        Execute a function using the existing Brimley argument and dispatch flow.
        """
        resolved_args = ArgumentResolver.resolve(func, tool_args, self.context)
        return self.dispatcher.run(func, resolved_args, self.context)

    def register_tools(self, mcp_server: Any = None) -> Any:
        """
        Register MCP-compatible tools on a server instance.

        This is a scaffold for M2.2+ and intentionally no-ops for now.
        """
        return mcp_server
