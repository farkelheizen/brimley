"""Parser for api_function YAML files (Brimley 0.7)."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from brimley.core.models import ApiFunction
from brimley.utils.secrets import validate_secrets_no_provider


def parse_api_file(file_path: Path) -> ApiFunction:
    """
    Parse a YAML file that declares ``type: api_function``.

    Validates that:
    - The YAML is syntactically valid.
    - All required fields are present (delegated to Pydantic).
    - No ``provider`` secret sources are declared (v0.7 restriction per ADR-0003).

    Args:
        file_path: Absolute path to the ``.yaml`` file.

    Returns:
        A validated :class:`ApiFunction` instance.

    Raises:
        ValueError: On YAML syntax errors, missing required fields, or
            ``provider`` secret sources (caught by Scanner as a diagnostic).
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Could not read file {file_path}: {exc}")

    try:
        data: dict = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {file_path}: {exc}")

    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {file_path}, got {type(data).__name__}.")

    try:
        func = ApiFunction(**data)
    except ValidationError as exc:
        raise ValueError(f"Validation error in {file_path}: {exc}")

    # Validate provider sources at scan time (ADR-0003).
    validate_secrets_no_provider(
        func.secrets,
        func_name=func.name,
        file_path=str(file_path),
    )

    return func
