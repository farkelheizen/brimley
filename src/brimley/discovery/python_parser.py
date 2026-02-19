from pathlib import Path
import ast
import re
import sys
from typing import Any, Union
from pydantic import ValidationError
from brimley.core.models import DiscoveredEntity, PythonFunction
from brimley.discovery.utils import parse_frontmatter


INJECTED_TYPE_NAMES = {
    "BrimleyContext",
    "Context",
    "MockMCPContext",
    "mcp.server.fastmcp.Context",
    "fastmcp.Context",
    "fastmcp.server.context.Context",
}

_FUNCTION_DECORATORS = {"function", "brimley.function"}
_ENTITY_DECORATORS = {"entity", "brimley.entity"}
_RELOAD_HAZARD_IDENTIFIERS = {"open", "connect", "start", "run", "thread", "popen", "call"}


def _decorator_name(node: ast.AST) -> str | None:
    """Return normalized decorator name from Name/Attribute/Call nodes."""
    target = node.func if isinstance(node, ast.Call) else node

    if isinstance(target, ast.Name):
        return target.id

    if isinstance(target, ast.Attribute):
        left = _decorator_name(target.value)
        if left:
            return f"{left}.{target.attr}"
        return target.attr

    return None


def _literal_or_none(node: ast.AST) -> Any | None:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _extract_decorator_kwargs(node: ast.AST) -> dict[str, Any]:
    if not isinstance(node, ast.Call):
        return {}

    kwargs: dict[str, Any] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            continue

        literal = _literal_or_none(keyword.value)
        if literal is not None:
            kwargs[keyword.arg] = literal

    return kwargs


def _normalize_for_type_lookup(annotation_name: str, aliases: dict[str, str]) -> str:
    if annotation_name in aliases:
        return aliases[annotation_name]
    return annotation_name


def _map_annotation_to_return_shape(annotation_name: str | None) -> str:
    if not annotation_name:
        return "void"

    normalized = annotation_name.strip()
    lower = normalized.lower()

    if lower in {"none", "nonetype"}:
        return "void"
    if lower in {"str", "string"}:
        return "string"
    if lower in {"int", "integer"}:
        return "int"
    if lower in {"float", "number"}:
        return "float"
    if lower in {"bool", "boolean"}:
        return "bool"
    if lower in {"dict", "object"}:
        return "dict"
    if lower in {"list", "array"}:
        return "list"

    list_match = re.fullmatch(r"(?:typing\.)?(?:list|List)\[(.+)\]", normalized)
    if list_match:
        inner = list_match.group(1).strip()
        inner_shape = _map_annotation_to_return_shape(inner)
        return f"{inner_shape}[]"

    return normalized.rsplit(".", 1)[-1]


def _find_brimley_decorators(tree: ast.Module) -> list[tuple[ast.AST, str, dict[str, Any]]]:
    """Find decorated function/class definitions relevant to Brimley."""
    matches: list[tuple[ast.AST, str, dict[str, Any]]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        for decorator in node.decorator_list:
            dec_name = _decorator_name(decorator)
            if not dec_name:
                continue

            kwargs = _extract_decorator_kwargs(decorator)
            if dec_name in _FUNCTION_DECORATORS and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                matches.append((node, "function", kwargs))
                break

            if dec_name in _ENTITY_DECORATORS and isinstance(node, ast.ClassDef):
                matches.append((node, "entity", kwargs))
                break

    return matches


def _call_identifier(call_node: ast.Call) -> str | None:
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id

    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr

    return None


def _scan_for_reload_hazards(tree: ast.Module) -> list[str]:
    """Detect top-level side-effect calls in modules with reload-enabled functions."""
    decorators = _find_brimley_decorators(tree)
    has_reload_enabled_function = any(
        kind == "function" and bool(kwargs.get("reload", True))
        for _, kind, kwargs in decorators
    )

    if not has_reload_enabled_function:
        return []

    hazards: list[str] = []
    for top_level_node in tree.body:
        if isinstance(top_level_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        for descendant in ast.walk(top_level_node):
            if not isinstance(descendant, ast.Call):
                continue

            identifier = _call_identifier(descendant)
            if not identifier:
                continue

            if identifier.lower() not in _RELOAD_HAZARD_IDENTIFIERS:
                continue

            line_number = getattr(descendant, "lineno", None)
            if line_number is not None:
                hazards.append(f"line {line_number}: {identifier}")
            else:
                hazards.append(identifier)

    return hazards


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

    if annotation_name in INJECTED_TYPE_NAMES:
        return True

    if annotation_name.rsplit(".", 1)[-1] in {"BrimleyContext", "Context", "MockMCPContext"}:
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
        normalized_annotation_name = (
            _normalize_for_type_lookup(annotation_name, aliases)
            if annotation_name is not None
            else None
        )
        from_context: str | None = None

        if isinstance(parameter.annotation, ast.Subscript):
            subscript_name = ast.unparse(parameter.annotation.value)
            if subscript_name.endswith("Annotated"):
                annotation_slice = parameter.annotation.slice
                elements: list[ast.AST]
                if isinstance(annotation_slice, ast.Tuple):
                    elements = list(annotation_slice.elts)
                else:
                    elements = [annotation_slice]

                if elements:
                    base_annotation_name = _extract_annotation_name(elements[0], aliases)
                    if base_annotation_name:
                        normalized_annotation_name = _normalize_for_type_lookup(base_annotation_name, aliases)

                for meta_node in elements[1:]:
                    if isinstance(meta_node, ast.Call):
                        meta_name = ast.unparse(meta_node.func).rsplit(".", 1)[-1]
                        if meta_name in {"AppState", "Config"} and meta_node.args:
                            key_literal = _literal_or_none(meta_node.args[0])
                            if isinstance(key_literal, str):
                                if meta_name == "AppState":
                                    from_context = f"app.{key_literal}"
                                elif meta_name == "Config":
                                    from_context = f"config.{key_literal}"
                                break

        if _is_injected_annotation(normalized_annotation_name):
            continue

        if normalized_annotation_name is None:
            arg_type: Any = "string"
        else:
            arg_type = _map_annotation_to_arg_type(normalized_annotation_name)

        has_default = idx >= defaults_offset
        arg_spec: Any

        if from_context:
            arg_spec = {"type": arg_type, "from_context": from_context}
        else:
            arg_spec = arg_type

        if has_default:
            default_value = defaults[idx - defaults_offset]
            try:
                parsed_default = ast.literal_eval(default_value)
            except Exception:
                parsed_default = ast.unparse(default_value)
            if isinstance(arg_spec, str):
                arg_spec = {"type": arg_spec}
            arg_spec["default"] = parsed_default
            inferred_inline[parameter.arg] = arg_spec
        else:
            inferred_inline[parameter.arg] = arg_spec

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

def _parse_legacy_frontmatter_python(tree: ast.Module, file_path: Path) -> list[Union[PythonFunction, DiscoveredEntity]]:
    """Legacy fallback parser for YAML frontmatter in module docstring."""
    docstring = ast.get_docstring(tree)
    if not docstring:
        return []

    try:
        meta, _ = parse_frontmatter(docstring)
    except ValueError as e:
        raise ValueError(f"Frontmatter parsing error in {file_path}: {e}")

    if not meta or meta.get("type") != "python_function":
        return []

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
        return [PythonFunction(**meta)]
    except ValidationError as e:
        raise ValueError(f"Validation error in {file_path}: {e}")


def parse_python_file(file_path: Path) -> list[Union[PythonFunction, DiscoveredEntity]]:
    """
    Parse a Python file via AST without importing/executing it.

    Returns discovered Brimley objects from decorators. For transition
    compatibility, falls back to legacy YAML-frontmatter Python functions.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ValueError(f"Could not read file {file_path}: {e}")

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        raise ValueError(f"Syntax error in Python file {file_path}: {e}")

    module_name = _infer_module_name(file_path)
    parsed_items: list[Union[PythonFunction, DiscoveredEntity]] = []

    for node, kind, kwargs in _find_brimley_decorators(tree):
        if kind == "function" and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_type = kwargs.get("type", "python_function")
            if function_type != "python_function":
                raise ValueError(
                    f"Unsupported decorated function type '{function_type}' in {file_path}. "
                    "AST parser currently supports python_function for this phase."
                )

            function_name = kwargs.get("name") if isinstance(kwargs.get("name"), str) else node.name
            arguments = _infer_arguments_from_handler(tree, node.name)

            mcp = None
            if kwargs.get("mcpType") == "tool":
                mcp = {"type": "tool"}

            return_annotation_name = _extract_annotation_name(node.returns, _build_import_aliases(tree))
            return_shape = _map_annotation_to_return_shape(return_annotation_name)

            meta = {
                "name": function_name,
                "type": "python_function",
                "description": ast.get_docstring(node),
                "handler": f"{module_name}.{node.name}",
                "reload": bool(kwargs.get("reload", True)),
                "return_shape": return_shape,
            }

            if arguments:
                meta["arguments"] = arguments
            if mcp is not None:
                meta["mcp"] = mcp

            try:
                parsed_items.append(PythonFunction(**meta))
            except ValidationError as e:
                raise ValueError(f"Validation error in {file_path}: {e}")

        elif kind == "entity" and isinstance(node, ast.ClassDef):
            entity_name = kwargs.get("name") if isinstance(kwargs.get("name"), str) else node.name
            entity_meta = {
                "name": entity_name,
                "type": "python_entity",
                "handler": f"{module_name}.{node.name}",
            }
            try:
                parsed_items.append(DiscoveredEntity(**entity_meta))
            except ValidationError as e:
                raise ValueError(f"Validation error in {file_path}: {e}")

    if parsed_items:
        return parsed_items

    return _parse_legacy_frontmatter_python(tree, file_path)
