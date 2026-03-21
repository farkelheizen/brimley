"""Pluggable ResultParser interface and built-in parsers (Brimley 0.7)."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from brimley.utils.diagnostics import BrimleyExecutionError


class ResultParser(ABC):
    """
    Abstract base for all result parsers.

    Each parser handles a specific output format (text, JSON, regex).
    The registry key (``type`` field in the ``results:`` block) selects
    the appropriate parser instance at runtime.

    Introduced in Brimley 0.7.
    """

    @abstractmethod
    def parse(self, body: bytes, config: Optional[Dict[str, Any]], func_name: str) -> Any:
        """
        Parse raw output bytes.

        Args:
            body:      Raw output (HTTP response body or subprocess stdout).
            config:    Parser-specific configuration from ``results.<code>.parse``.
                       May be ``None`` for parsers that don't require config.
            func_name: Function name (for error messages).

        Returns:
            Parsed value appropriate for ``return_shape`` mapping.
        """


class TextResultParser(ResultParser):
    """
    Decodes bytes to UTF-8 string and returns it unchanged.

    ``parse`` config is ignored.
    """

    def parse(self, body: bytes, config: Optional[Dict[str, Any]], func_name: str) -> Any:
        return body.decode("utf-8", errors="replace")


class JsonResultParser(ResultParser):
    """
    Decodes bytes as JSON.

    If ``config.path`` is set, extracts a sub-value using a custom dot-path
    expression (see :func:`_dot_path_extract` for syntax).
    """

    def parse(self, body: bytes, config: Optional[Dict[str, Any]], func_name: str) -> Any:
        text = body.decode("utf-8", errors="replace")
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BrimleyExecutionError(
                message=f"Failed to parse output as JSON: {exc}",
                func_name=func_name,
            ) from exc

        if config and config.get("path"):
            data = _dot_path_extract(data, config["path"], func_name)

        return data


class RegexResultParser(ResultParser):
    """
    Applies a regex pattern to the decoded UTF-8 string.

    Extracts ``config.capture_group`` (named group) if specified,
    otherwise returns the full match.  Returns ``None`` on no match.

    ``config.pattern`` is required.  ``config.capture_group`` is optional.
    """

    def parse(self, body: bytes, config: Optional[Dict[str, Any]], func_name: str) -> Any:
        if not config or not config.get("pattern"):
            raise BrimleyExecutionError(
                message="'regex' parser requires a 'pattern' in the 'parse' config.",
                func_name=func_name,
            )
        text = body.decode("utf-8", errors="replace")
        match = re.search(config["pattern"], text)
        if not match:
            return None
        if config.get("capture_group"):
            try:
                return match.group(config["capture_group"])
            except (IndexError, KeyError):
                return match.group(0)
        return match.group(0)


# ---------------------------------------------------------------------------
# Parser registry
# ---------------------------------------------------------------------------

_RESULT_PARSERS: Dict[str, ResultParser] = {
    "text": TextResultParser(),
    "json": JsonResultParser(),
    "regex": RegexResultParser(),
}


def get_parser(type_name: str, func_name: str) -> ResultParser:
    """
    Look up a result parser by name.

    Raises :class:`BrimleyExecutionError` if the name is unknown.
    """
    parser = _RESULT_PARSERS.get(type_name.lower())
    if parser is None:
        available = ", ".join(sorted(_RESULT_PARSERS))
        raise BrimleyExecutionError(
            message=(
                f"Unknown result parser '{type_name}'. "
                f"Available parsers: {available}."
            ),
            func_name=func_name,
        )
    return parser


# ---------------------------------------------------------------------------
# Dot-path extractor (custom, no third-party dependency)
# ---------------------------------------------------------------------------

def _dot_path_extract(data: Any, path: str, func_name: str) -> Any:
    """
    Extract a value from a nested structure using a custom dot-path expression.

    Supported syntax:
    - ``"key"``               — top-level key
    - ``"a.b.c"``             — nested key traversal
    - ``"items[0]"``          — list index access
    - ``"items[*].name"``     — list-member projection (returns a list)

    This is a lightweight alternative to JSONPath — no third-party dependency.
    """
    if not path:
        return data

    segments = _split_path(path)
    return _traverse(data, segments, func_name)


def _split_path(path: str) -> list[str]:
    """Split a dot-path expression into segments, preserving bracket notation."""
    # Replace [N] with .[N] so bracket access becomes a regular segment
    normalised = re.sub(r"\[(\d+|\*)\]", r".[\1]", path)
    # Split on dots, strip empty strings from leading dot
    return [s for s in normalised.split(".") if s]


def _traverse(data: Any, segments: list[str], func_name: str) -> Any:
    current = data
    for seg in segments:
        if seg == "[*]":
            # Projection: apply remaining path to each list element
            if not isinstance(current, list):
                return current
            # Already consumed this segment; return all elements
            return current
        idx_match = re.fullmatch(r"\[(\d+)\]", seg)
        if idx_match:
            idx = int(idx_match.group(1))
            if isinstance(current, list):
                try:
                    current = current[idx]
                except IndexError:
                    return None
            else:
                return current
        elif isinstance(current, dict):
            current = current.get(seg)
        else:
            return current
    return current


def _traverse_projection(data: Any, segments: list[str], func_name: str) -> Any:
    """Handle [*] projection — apply remaining segments to each list member."""
    if not isinstance(data, list):
        return data
    return [_traverse(item, segments, func_name) for item in data]
