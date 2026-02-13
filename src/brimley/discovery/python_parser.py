from pathlib import Path
import ast
import sys
from pydantic import ValidationError
from brimley.core.models import PythonFunction
from brimley.discovery.utils import parse_frontmatter


def _infer_module_name(file_path: Path) -> str:
    """
    Infer a Python module name for a file path using active sys.path roots.
    """
    resolved_path = file_path.resolve()

    for search_path in sys.path:
        if not search_path:
            continue

        try:
            base = Path(search_path).resolve()
            relative = resolved_path.relative_to(base)
        except Exception:
            continue

        if relative.suffix != ".py":
            continue

        module_parts = relative.with_suffix("").parts
        if module_parts:
            return ".".join(module_parts)

    return file_path.stem

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
    
    handler = meta.get("handler")
    if isinstance(handler, str) and "." not in handler:
        module_name = _infer_module_name(file_path)
        meta["handler"] = f"{module_name}.{handler}"

    try:
        return PythonFunction(**meta)
    except ValidationError as e:
        raise ValueError(f"Validation error in {file_path}: {e}")
