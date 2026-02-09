import sys
import inspect
from typing import Any, Dict, Optional, Type
from pydantic import Field

# We assume fastmcp is installed if this module is being used.
try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = Any

class BrimleyMCPAdapter:
    """
    Adapts BrimleyEngine tools into FastMCP compatible tool definitions.
    """
    def __init__(self, brimley_engine: Any, mcp_server: FastMCP):
        """
        :param brimley_engine: An initialized BrimleyEngine instance.
        :param mcp_server: An initialized FastMCP instance.
        """
        self.engine = brimley_engine
        self.mcp = mcp_server
        self.type_map = {
            "int": int,
            "integer": int, 
            "string": str, 
            "float": float, 
            "boolean": bool, 
            "bool": bool
        }

    def register_tools(self) -> int:
        """
        Iterates through Brimley tools and registers them with the MCP server.
        Returns the count of registered tools.
        """
        count = 0
        # Access internal tools dictionary - usually _tools
        # Implementation relying on internal structure of BrimleyEngine
        if not hasattr(self.engine, "_tools"):
             print("Error: BrimleyEngine does not have _tools attribute. Adapter may be incompatible.", file=sys.stderr)
             return 0

        for name, tool_def in self.engine._tools.items():
            try:
                self._register_single_tool(name, tool_def)
                count += 1
                # Log to stderr to avoid polluting stdout (MCP protocol)
                print(f"Registered tool: {name}", file=sys.stderr)
            except Exception as e:
                print(f"Failed to register tool {name}: {e}", file=sys.stderr)
        
        return count

    def _register_single_tool(self, name: str, tool_def: Any):
        """
        Generates a dynamic wrapper function for a tool and registers it with FastMCP.
        Uses `exec` to create a function with a signature that matches the tool arguments,
        which is required for proper introspection by FastMCP/Claude.
        """
        description = tool_def.description
        
        args_str_parts = []
        doc_str_parts = []
        
        # Build argument signature strings
        for arg in tool_def.arguments.inline:
            py_type = self.type_map.get(arg.type.lower(), str)
            py_type_name = py_type.__name__
            
            if arg.required:
                args_str_parts.append(f"{arg.name}: {py_type_name}")
            else:
                def_val = repr(arg.default)
                args_str_parts.append(f"{arg.name}: {py_type_name} = {def_val}")
            
            doc_str_parts.append(f":param {arg.name}: Argument of type {arg.type}")

        sig_str = ", ".join(args_str_parts)
        doc_str = "\n    ".join(doc_str_parts)
        
        # Define the function body as a string
        # We capture 'engine' in the local closure when we exec
        func_code = f"""
def {name}({sig_str}):
    \"\"\"
    {description}
    
    {doc_str}
    \"\"\"
    # Capture locals before doing anything else to get arguments
    import inspect
    args = locals().copy()
    if 'inspect' in args: del args['inspect']
    
    # Execute via the bound engine
    return str(engine.execute_tool('{name}', args))
"""
        
        # Execute in a custom global scope so the function can resolve 'engine'
        # Functions defined in exec() treat the passed globals dict as their module scope
        global_scope = {"engine": self.engine, "inspect": inspect}
        
        # This creates the function '{name}' in global_scope
        exec(func_code, global_scope)
        generated_func = global_scope[name]
        
        # Register with MCP
        # FastMCP uses the function's __name__ and docstring, which we just set
        self.mcp.tool(name=name, description=description)(generated_func)
