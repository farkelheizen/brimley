import os
import sys
from pathlib import Path
from fastmcp import FastMCP

# Add source directory to sys.path to ensure 'brimley' is importable 
# without needing an explicit pip install -e . in development.
CURRENT_DIR = Path(__file__).parent.resolve()
SRC_PATH = CURRENT_DIR.parent.parent / "src"
if SRC_PATH.exists() and str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from brimley.core import BrimleyEngine

# Configuration paths
TOOLS_DIR = CURRENT_DIR / "tools"
DB_PATH = CURRENT_DIR / "demo.db"

EXTENSIONS_FILE = CURRENT_DIR / "extensions.py"

# Initialize Brimley Engine
# Ensure the DB exists
if not DB_PATH.exists():
    print("Database not found. Running setup_db.py...")
    import setup_db
    setup_db.init_db()

engine = BrimleyEngine(
    tools_dir=str(TOOLS_DIR),
    db_path=str(DB_PATH),
    extensions_file=str(EXTENSIONS_FILE)
)

# Initialize MCP Server
mcp = FastMCP("Brimley Demo")

import inspect
from pydantic import create_model, Field
from typing import Optional, Type

def register_brimley_tools():
    """
    Iterates over loaded Brimley tools and registers them with FastMCP.
    Uses dynamic Pydantic model creation to satisfy FastMCP's introspection.
    """
    import sys
    print(f"DEBUG: Scanning for Brimley tools...", file=sys.stderr)
    print(f"DEBUG: Tools Dir: {TOOLS_DIR}", file=sys.stderr)
    print(f"DEBUG: Engine loaded: {list(engine._tools.keys())}", file=sys.stderr)

    count = 0
    type_map = {
        "int": int,
        "integer": int, 
        "string": str, 
        "float": float, 
        "boolean": bool, 
        "bool": bool
    }

    for name, tool_def in engine._tools.items():
        description = tool_def.description
        print(f"  - Registering tool: {name}", file=sys.stderr)
        
        # Build Pydantic model fields from Brimley arguments
        fields = {}
        for arg in tool_def.arguments.inline:
            py_type = type_map.get(arg.type.lower(), str)
            if arg.required:
                fields[arg.name] = (py_type, Field(..., description=f"Argument {arg.name}"))
            else:
                default_val = arg.default
                fields[arg.name] = (Optional[py_type], Field(default_val, description=f"Argument {arg.name}"))
        
        # Create a dynamic Pydantic model named after the tool
        # FastMCP (and others) often inspect the signature. 
        # By creating a function that takes this model as an argument, we might satisfy it?
        # FastMCP supports: def tool(arg1: int, arg2: str)
        # It DOES NOT usually support: def tool(model: PydanticModel) unless explicitly unwrapped?
        # Actually, the error said "Functions with **kwargs are not supported".
        # It implies it wants named arguments.
        
        # We will use 'make_fun' logic manually via 'exec' to create a properly signatured function
        # because this is the most robust way to fool inspection-based libraries.
        
        args_str_parts = []
        doc_str_parts = []
        
        for arg in tool_def.arguments.inline:
            py_type_name = type_map.get(arg.type.lower(), str).__name__
            if arg.required:
                args_str_parts.append(f"{arg.name}: {py_type_name}")
            else:
                def_val = repr(arg.default)
                args_str_parts.append(f"{arg.name}: {py_type_name} = {def_val}")
            
            doc_str_parts.append(f":param {arg.name}: Argument of type {arg.type}")

        sig_str = ", ".join(args_str_parts)
        doc_str = "\n".join(doc_str_parts)
        
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
    
    # Brimley expects a dict
    return str(engine.execute_tool('{name}', args))
"""
        
        # Execute in a safe scope
        local_scope = {"engine": engine}
        try:
            exec(func_code, local_scope)
            generated_func = local_scope[name]
            
            # Register with MCP
            mcp.tool(name=name, description=description)(generated_func)
            count += 1
        except Exception as e:
             print(f"Failed to generate dynamic function for {name}: {e}", file=sys.stderr)

    print(f"Registered {count} tools.", file=sys.stderr)

# Register them
register_brimley_tools()

if __name__ == "__main__":
    # fastmcp run server.py
    mcp.run()
