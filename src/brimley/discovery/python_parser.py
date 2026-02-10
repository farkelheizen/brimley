from pathlib import Path
import ast
import yaml
from brimley.core.models import PythonFunction
from brimley.discovery.utils import parse_frontmatter

def parse_python_file(file_path: Path) -> PythonFunction:
    """
    Parses a .py file looking for frontmatter in the module docstring.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ValueError(f"Could not read file {file_path}: {e}")

    # Use AST to extract docstring safely vs regex which is brittle with python code
    try:
        tree = ast.parse(content)
        docstring = ast.get_docstring(tree)
    except SyntaxError as e:
        raise ValueError(f"Syntax error in Python file {file_path}: {e}")
        
    if not docstring:
        raise ValueError("No docstring found containing frontmatter metadata.")

    # Parse yaml from docstring
    # Docstring might contain the frontmatter wrapped in ---
    try:
        meta, _ = parse_frontmatter(docstring)
    except ValueError as e:
        raise ValueError(f"Frontmatter parsing error in {file_path}: {e}")
        
    # We don't necessarily extract "body" for PythonFunction, 
    # but we DO need to determine the handler.
    # If handler is not explicitly set in frontmatter, we might infer it?
    # For now, require 'handler' in frontmatter or infer from filename + default function name?
    # Let's require it.
    
    try:
        return PythonFunction(**meta)
    except Exception as e:
        raise ValueError(f"Validation error: {e}")
