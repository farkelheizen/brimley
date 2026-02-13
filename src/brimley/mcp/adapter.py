import importlib
import importlib.util
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

    def is_fastmcp_available(self) -> bool:
        """
        Check whether the optional fastmcp package is installed.
        """
        return importlib.util.find_spec("fastmcp") is not None

    def require_fastmcp(self) -> Any:
        """
        Resolve and return the FastMCP class, raising a clear error if unavailable.
        """
        if not self.is_fastmcp_available():
            raise RuntimeError("MCP tools found but 'fastmcp' is not installed. Install with: pip install fastmcp")

        module = importlib.import_module("fastmcp")
        return module.FastMCP

    def register_tools(self, mcp_server: Any = None) -> Any:
        """
        Register discovered MCP tools on the provided (or newly created) MCP server.
        """
        tools = self.discover_tools()
        if not tools:
            return mcp_server

        if mcp_server is None:
            FastMCP = self.require_fastmcp()
            mcp_server = FastMCP(name="BrimleyTools")

        if not hasattr(mcp_server, "add_tool"):
            raise ValueError("Invalid MCP server: missing required 'add_tool' method")

        for func in tools:
            wrapper = self.create_tool_wrapper(func)
            try:
                mcp_server.add_tool(wrapper)
            except Exception as exc:
                raise ValueError(f"Failed to register MCP tool '{func.name}': {exc}") from exc

        return mcp_server
