import importlib
import importlib.util
import json
from typing import Any, Dict, Tuple, Type

from pydantic import BaseModel, Field, create_model
from pydantic.fields import PydanticUndefined

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

    def get_tool_schema_signatures(self, tools: list[BrimleyFunction] | None = None) -> Dict[str, str]:
        """Return deterministic MCP tool schema signatures keyed by tool name."""
        selected_tools = tools if tools is not None else self.discover_tools()
        signatures: Dict[str, str] = {}

        for func in selected_tools:
            input_model = self.build_tool_input_model(func)
            schema_payload = {
                "tool": func.name,
                "input_schema": input_model.model_json_schema(),
            }
            signatures[func.name] = json.dumps(schema_payload, sort_keys=True)

        return signatures

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
        input_model = self.build_tool_input_model(func)
        
        # Create function signature based on input model fields
        field_names = list(input_model.model_fields.keys())
        
        # Build parameter list with defaults
        params = []
        defaults = {}
        context_type = self._resolve_fastmcp_context_type()
        for field_name in field_names:
            field_info = input_model.model_fields[field_name]
            annotation = field_info.annotation
            if field_info.default is not PydanticUndefined:
                defaults[field_name] = field_info.default
                params.append(f"{field_name}: {annotation.__name__} = {repr(field_info.default)}")
            else:
                params.append(f"{field_name}: {annotation.__name__}")
        
        # Create the function code
        param_list = ", ".join(params)
        arg_dict_items = [f'"{name}": {name}' for name in field_names]
        arg_dict = "{" + ", ".join(arg_dict_items) + "}"

        if param_list:
            wrapper_params = f"{param_list}, *, ctx: ContextType = None"
        else:
            wrapper_params = "*, ctx: ContextType = None"
        
        func_code = f"""
def wrapper({wrapper_params}):
    return self.execute_tool(func, {arg_dict}, runtime_injections={{"mcp_context": ctx}} if ctx is not None else None)
"""
        
        # Execute the code to create the function
        local_vars = {"self": self, "func": func, "PydanticUndefined": PydanticUndefined}
        exec(func_code, {"self": self, "func": func, "ContextType": context_type}, local_vars)
        wrapper = local_vars["wrapper"]
        
        wrapper.__name__ = func.name
        wrapper.__doc__ = (func.mcp.description if getattr(func, "mcp", None) and func.mcp.description else func.description) or ""
        return wrapper

    def _resolve_fastmcp_context_type(self) -> type[Any]:
        """
        Resolve FastMCP Context type when available; fall back to Any for local/non-MCP execution.
        """
        try:
            context_module = importlib.import_module("fastmcp.server.context")
            context_type = getattr(context_module, "Context", None)
            if isinstance(context_type, type):
                return context_type
        except Exception:
            pass

        return Any

    def execute_tool(
        self,
        func: BrimleyFunction,
        tool_args: Dict[str, Any],
        runtime_injections: Dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute a tool by resolving arguments and dispatching to the appropriate runner.
        """
        resolved_args = ArgumentResolver.resolve(func, tool_args, self.context)
        return self.dispatcher.run(func, resolved_args, self.context, runtime_injections=runtime_injections)

    def create_tool_object(self, func: BrimleyFunction) -> Any:
        """
        Create a FastMCP Tool object for the given function.
        """
        input_model = self.build_tool_input_model(func)
        wrapper = self.create_tool_wrapper(func)
        
        # Import Tool from fastmcp.tools
        fastmcp_module = importlib.import_module("fastmcp")
        tools_module = getattr(fastmcp_module, 'tools', None)
        if tools_module:
            Tool = getattr(tools_module, 'Tool', None)
        else:
            Tool = None
        
        if Tool is None:
            raise RuntimeError("FastMCP Tool class not found")
        
        # Use from_function to create the tool, which will auto-generate the parameters schema
        tool = Tool.from_function(
            fn=wrapper,
            name=func.name,
            description=(func.mcp.description if getattr(func, "mcp", None) and func.mcp.description else func.description) or "",
        )
        
        # Override the parameters schema with our custom one
        tool.parameters = input_model.model_json_schema()
        
        return tool

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
            tool_obj = self.create_tool_object(func)
            try:
                mcp_server.add_tool(tool_obj)
            except Exception as exc:
                raise ValueError(f"Failed to register MCP tool '{func.name}': {exc}") from exc

        return mcp_server
