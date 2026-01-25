from typing import Dict, Any, Optional
import importlib.util
import sys
from pathlib import Path
from brimley.config import load_tools_from_directory
from brimley.schemas import ToolDefinition, ToolType
from brimley.validation import validate_tool_arguments
from brimley.backend.runner import run_local_sql

class BrimleyEngine:
    """
    The main entry point for executing tools.
    Loads tools on initialization and dispatches execution requests.
    """
    
    def __init__(self, tools_dir: str, db_path: str, extensions_file: Optional[str] = None):
        self.db_path = db_path
        self.tools_dir = tools_dir
        self.extensions_file = extensions_file
        
        # Load extensions (UDFs) before loading tools, so they are available
        if self.extensions_file:
            self._load_extensions()

        self._tools: Dict[str, ToolDefinition] = {}
        self._load_tools()

    def _load_extensions(self):
        """Dynamically imports the extensions module to trigger decorator registration."""
        path = Path(self.extensions_file).resolve()
        if not path.exists():
             # Warning or Error? Let's print a warning for now to avoid crashing default setups if config is stale
             print(f"Warning: Extensions file not found at {path}")
             return

        module_name = "brimley_extensions_loaded"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
        except Exception as e:
            print(f"Failed to load extensions file {path}: {e}")


    def _load_tools(self):
        """Loads tools from directory and validates them into ToolDefinitions."""
        raw_tools = load_tools_from_directory(self.tools_dir)
        for name, raw_def in raw_tools.items():
            # Parse into Pydantic model
            # If validation fails here, we might want to log and skip (handled in P1/ConfigLoader?)
            # ConfigLoader just loads JSON. We validate schema compliance here or there?
            # ConfigLoader was P1.S2. It returns Dict.
            # We convert to ToolDefinition here.
            try:
                tool_def = ToolDefinition(**raw_def)
                self._tools[name] = tool_def
            except Exception as e:
                # Log error in production
                print(f"Failed to load tool {name}: {e}")
                continue

    def execute_tool(self, tool_name: str, raw_args: Dict[str, Any]) -> Any:
        """
        Executes a named tool with the provided arguments.
        
        1. Lookup tool
        2. Validate arguments
        3. Dispatch to backend
        """
        tool_def = self._tools.get(tool_name)
        if not tool_def:
            raise KeyError(f"Tool '{tool_name}' not found.")

        # Validation (P2)
        validated_args = validate_tool_arguments(tool_def, raw_args)

        # Dispatch (P3)
        if tool_def.tool_type == ToolType.LOCAL_SQL:
            return run_local_sql(tool_def, validated_args, self.db_path)
        
        elif tool_def.tool_type == ToolType.PROMPT_BUILDER:
            raise NotImplementedError("PROMPT_BUILDER not yet implemented.")
            
        else:
             raise ValueError(f"Unknown tool type: {tool_def.tool_type}")

    def get_tool_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_name)
