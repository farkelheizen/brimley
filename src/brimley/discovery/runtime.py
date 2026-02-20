from __future__ import annotations

import inspect
from types import ModuleType
from typing import Any, Annotated, Union, get_args, get_origin

from pydantic import ValidationError

from brimley.core.di import AppState, Config
from brimley.core.models import DiscoveredEntity, PythonFunction, SqlFunction, TemplateFunction

_INJECTED_TYPE_NAMES = {
    "BrimleyContext",
    "Context",
    "MockMCPContext",
    "mcp.server.fastmcp.Context",
    "fastmcp.Context",
    "fastmcp.server.context.Context",
}


def _type_to_name(annotation: Any) -> str | None:
    if annotation is inspect.Signature.empty:
        return None

    if isinstance(annotation, str):
        return annotation

    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        if args:
            return _type_to_name(args[0])
        return None

    if origin in {list, tuple, set}:
        return "list"

    if origin in {dict}:
        return "dict"

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation)


def _annotation_to_arg_type(annotation: Any) -> str:
    name = (_type_to_name(annotation) or "string").rsplit(".", 1)[-1].lower()

    if name in {"str", "string"}:
        return "string"
    if name in {"int", "integer"}:
        return "int"
    if name in {"float", "number"}:
        return "float"
    if name in {"bool", "boolean"}:
        return "bool"
    if name in {"list", "array"}:
        return "list"
    if name in {"dict", "object"}:
        return "dict"
    return "any"


def _annotation_to_return_shape(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return "void"

    if annotation is None or annotation is type(None):
        return "void"

    origin = get_origin(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        if args:
            return _annotation_to_return_shape(args[0])

    if origin in {list, tuple, set}:
        args = get_args(annotation)
        if args:
            return f"{_annotation_to_return_shape(args[0])}[]"
        return "list"

    name = _type_to_name(annotation)
    if not name:
        return "void"

    lower = name.lower()
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

    return name.rsplit(".", 1)[-1]


def _is_injected_annotation(annotation: Any) -> bool:
    name = _type_to_name(annotation)
    if not name:
        return False

    if name in _INJECTED_TYPE_NAMES:
        return True

    return name.rsplit(".", 1)[-1] in {"BrimleyContext", "Context", "MockMCPContext"}


def _infer_arguments_for_callable(target: Any) -> dict[str, Any] | None:
    signature = inspect.signature(target)
    inline: dict[str, Any] = {}

    for parameter in signature.parameters.values():
        if parameter.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue

        annotation = parameter.annotation
        from_context: str | None = None

        if _is_injected_annotation(annotation):
            continue

        if get_origin(annotation) is Annotated:
            annotation_args = list(get_args(annotation))
            if annotation_args:
                annotation = annotation_args[0]
            for metadata in annotation_args[1:]:
                if isinstance(metadata, AppState):
                    from_context = f"app.{metadata.key}"
                    break
                if isinstance(metadata, Config):
                    from_context = f"config.{metadata.key}"
                    break

        arg_type = _annotation_to_arg_type(annotation)

        spec: Any = {"type": arg_type} if from_context else arg_type
        if from_context:
            spec["from_context"] = from_context

        if parameter.default is not inspect.Signature.empty:
            if isinstance(spec, str):
                spec = {"type": spec}
            spec["default"] = parameter.default

        inline[parameter.name] = spec

    if not inline:
        return None

    return {"inline": inline}


def _coerce_mcp(meta: dict[str, Any], extras: dict[str, Any]) -> dict[str, Any] | None:
    if meta.get("mcpType") == "tool":
        return {"type": "tool"}

    maybe_mcp = extras.get("mcp")
    if isinstance(maybe_mcp, dict) and maybe_mcp.get("type") == "tool":
        return {"type": "tool", **({"description": maybe_mcp.get("description")} if maybe_mcp.get("description") else {})}

    return None


def _build_python_function(module: ModuleType, target: Any, meta: dict[str, Any]) -> PythonFunction:
    extras = dict(meta.get("extra") or {})
    mcp = _coerce_mcp(meta, extras)

    model_data: dict[str, Any] = {
        "name": meta.get("name") or target.__name__,
        "type": "python_function",
        "handler": f"{module.__name__}.{target.__name__}",
        "description": inspect.getdoc(target),
        "reload": bool(meta.get("reload", True)),
        "return_shape": extras.get("return_shape") or _annotation_to_return_shape(inspect.signature(target).return_annotation),
    }

    arguments = extras.get("arguments")
    if not isinstance(arguments, dict):
        arguments = _infer_arguments_for_callable(target)
    if arguments:
        model_data["arguments"] = arguments

    if mcp is not None:
        model_data["mcp"] = mcp

    return PythonFunction(**model_data)


def _build_sql_function(target: Any, meta: dict[str, Any]) -> SqlFunction:
    extras = dict(meta.get("extra") or {})
    mcp = _coerce_mcp(meta, extras)

    model_data: dict[str, Any] = {
        "name": meta.get("name") or target.__name__,
        "type": "sql_function",
        "description": inspect.getdoc(target),
        "return_shape": extras.get("return_shape", "void"),
        "connection": extras.get("connection", "default"),
        "sql_body": extras.get("sql_body") or extras.get("sql") or extras.get("content") or "",
    }
    if mcp is not None:
        model_data["mcp"] = mcp

    return SqlFunction(**model_data)


def _build_template_function(target: Any, meta: dict[str, Any]) -> TemplateFunction:
    extras = dict(meta.get("extra") or {})
    mcp = _coerce_mcp(meta, extras)

    model_data: dict[str, Any] = {
        "name": meta.get("name") or target.__name__,
        "type": "template_function",
        "description": inspect.getdoc(target),
        "return_shape": extras.get("return_shape", "string"),
        "template_engine": extras.get("template_engine", "jinja2"),
        "template_body": extras.get("template_body") or extras.get("template") or extras.get("content"),
    }

    if isinstance(extras.get("messages"), list):
        model_data["messages"] = extras.get("messages")

    if mcp is not None:
        model_data["mcp"] = mcp

    return TemplateFunction(**model_data)


def _build_entity(module: ModuleType, target: type, meta: dict[str, Any]) -> DiscoveredEntity:
    return DiscoveredEntity(
        name=meta.get("name") or target.__name__,
        type="python_entity",
        handler=f"{module.__name__}.{target.__name__}",
        raw_definition=dict(meta.get("extra") or {}),
    )


def scan_module(module_obj: ModuleType) -> list[Union[PythonFunction, SqlFunction, TemplateFunction, DiscoveredEntity]]:
    """Discover Brimley models from a loaded module using `_brimley_meta` reflection."""
    discovered: list[Union[PythonFunction, SqlFunction, TemplateFunction, DiscoveredEntity]] = []

    for _, member in inspect.getmembers(module_obj):
        meta = getattr(member, "_brimley_meta", None)
        if not isinstance(meta, dict):
            continue

        member_module = getattr(member, "__module__", None)
        if member_module != module_obj.__name__:
            continue

        member_type = str(meta.get("type") or "python_function")

        try:
            if inspect.isfunction(member) or inspect.ismethod(member):
                if member_type == "python_function":
                    discovered.append(_build_python_function(module_obj, member, meta))
                elif member_type == "sql_function":
                    discovered.append(_build_sql_function(member, meta))
                elif member_type == "template_function":
                    discovered.append(_build_template_function(member, meta))

            elif inspect.isclass(member) and member_type in {"python_entity", "entity"}:
                discovered.append(_build_entity(module_obj, member, meta))
        except ValidationError:
            continue

    return discovered
