from pathlib import Path
import ast
import sys
from typing import Any
from pydantic import ValidationError
from brimley.core.models import PythonFunction
from brimley.discovery.utils import parse_frontmatter


INJECTED_TYPES = {"BrimleyContext", "mcp.server.fastmcp.Context"}


def _build_import_aliases(tree: ast.Module) -> dict[str, str]:
    """
    Build a best-effort alias map from module imports for annotation resolution.
    """
    aliases: dict[str, str] = {}

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            for imported_name in node.names:
                local_name = imported_name.asname or imported_name.name
                aliases[local_name] = f"{module_name}.{imported_name.name}" if module_name else imported_name.name
        elif isinstance(node, ast.Import):
            for imported_name in node.names:
                local_name = imported_name.asname or imported_name.name
                aliases[local_name] = imported_name.name

    return aliases


def _map_annotation_to_arg_type(annotation_name: str) -> str:
    """
    Map Python annotation names to Brimley argument type names.
    """
    base = annotation_name.rsplit(".", 1)[-1].lower()

    if base in {"str", "string"}:
        return "string"
    if base in {"int", "integer"}:
        return "int"
    if base in {"float", "number"}:
        return "float"
    if base in {"bool", "boolean"}:
        return "bool"
    if base in {"list", "array"}:
        return "list"
    if base in {"dict", "object"}:
        return "dict"
    return "any"


def _extract_annotation_name(annotation: ast.AST | None, aliases: dict[str, str]) -> str | None:
    """
    Convert an annotation AST node into a normalized type-name string.
    """
    if annotation is None:
        return None

    raw = ast.unparse(annotation)
    if raw.startswith("Annotated[") and raw.endswith("]"):
        inner = raw[len("Annotated[") : -1]
        raw = inner.split(",", 1)[0].strip()

    if raw in aliases:
        return aliases[raw]

    return raw


def _is_injected_annotation(annotation_name: str | None) -> bool:
    """
    Determine whether an annotation refers to a system-injected type.
    """
    if not annotation_name:
        return False

    if annotation_name in INJECTED_TYPES:
        return True

    if annotation_name.rsplit(".", 1)[-1] == "BrimleyContext":
        return True

    return False


def _infer_arguments_from_handler(tree: ast.Module, handler_name: str) -> dict[str, Any]:
    """
    Infer Brimley inline argument definitions from a handler function signature.
    """
    aliases = _build_import_aliases(tree)
    function_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == handler_name
        ),
        None,
    )

    if function_node is None:
        return {}

    params = list(function_node.args.args)
    defaults = list(function_node.args.defaults)
    defaults_offset = len(params) - len(defaults)

    inferred_inline: dict[str, Any] = {}

    for idx, parameter in enumerate(params):
        annotation_name = _extract_annotation_name(parameter.annotation, aliases)
        if _is_injected_annotation(annotation_name):
            continue

        if annotation_name is None:
            arg_type: Any = "string"
        else:
            arg_type = _map_annotation_to_arg_type(annotation_name)

        has_default = idx >= defaults_offset
        if has_default:
            default_value = defaults[idx - defaults_offset]
            try:
                parsed_default = ast.literal_eval(default_value)
            except Exception:
                parsed_default = ast.unparse(default_value)
            inferred_inline[parameter.arg] = {
                "type": arg_type,
                "default": parsed_default,
            }
        else:
            inferred_inline[parameter.arg] = arg_type

    return {"inline": inferred_inline} if inferred_inline else {}


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


def _infer_handler_name(tree: ast.Module, configured_name: str | None) -> str | None:
    """
    Infer the Python callable name when `handler` is omitted.
    """
    function_names = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    if configured_name and configured_name in function_names:
        return configured_name

    if len(function_names) == 1:
        return function_names[0]

    return None

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
    module_name = _infer_module_name(file_path)

    if isinstance(handler, str) and "." not in handler:
        meta["handler"] = f"{module_name}.{handler}"
    elif not handler:
        inferred_handler_name = _infer_handler_name(tree, meta.get("name"))
        if inferred_handler_name:
            meta["handler"] = f"{module_name}.{inferred_handler_name}"

    if not meta.get("arguments"):
        handler_path = meta.get("handler")
        if isinstance(handler_path, str):
            handler_name = handler_path.rsplit(".", 1)[-1]
            inferred_arguments = _infer_arguments_from_handler(tree, handler_name)
            if inferred_arguments:
                meta["arguments"] = inferred_arguments

    try:
        return PythonFunction(**meta)
    except ValidationError as e:
        raise ValueError(f"Validation error in {file_path}: {e}")
