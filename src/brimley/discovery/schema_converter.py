from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SchemaConversionIssue(BaseModel):
    """Structured converter issue used in human and machine-readable reports."""

    severity: Literal["warning", "error"]
    code: str
    path: str
    message: str


class SchemaConversionReport(BaseModel):
    """Summary report for JSON Schema conversion."""

    converted_fields: int = 0
    warnings: int = 0
    errors: int = 0
    issues: list[SchemaConversionIssue] = Field(default_factory=list)


class SchemaConversionResult(BaseModel):
    """Converter output containing FieldSpec inline map and diagnostics report."""

    inline: dict[str, Any] = Field(default_factory=dict)
    report: SchemaConversionReport = Field(default_factory=SchemaConversionReport)


_SUPPORTED_ROOT_KEYS: set[str] = {"type", "properties", "required", "additionalProperties"}
_SUPPORTED_PROPERTY_KEYS: set[str] = {
    "type",
    "format",
    "description",
    "default",
    "enum",
    "minimum",
    "maximum",
    "pattern",
    "items",
}
_UNSUPPORTED_HARD_KEYWORDS: set[str] = {
    "oneOf",
    "anyOf",
    "allOf",
    "not",
    "$ref",
    "$defs",
    "if",
    "then",
    "else",
    "dependencies",
    "dependentRequired",
    "dependentSchemas",
}


def convert_json_schema_to_fieldspec(schema: dict[str, Any], allow_lossy: bool = False) -> SchemaConversionResult:
    """Convert constrained JSON Schema to Brimley inline FieldSpec representation."""

    result = SchemaConversionResult()

    if not isinstance(schema, dict):
        _add_issue(
            result,
            severity="error",
            code="ERR_SCHEMA_INVALID_ROOT",
            path="$",
            message="Input schema must be a JSON object.",
        )
        return result

    if schema.get("type") != "object":
        _add_issue(
            result,
            severity="error",
            code="ERR_SCHEMA_ROOT_TYPE",
            path="$.type",
            message="Root schema type must be 'object'.",
        )
        return result

    _handle_unknown_keys(
        result=result,
        location="$",
        payload=schema,
        supported_keys=_SUPPORTED_ROOT_KEYS,
        allow_lossy=allow_lossy,
    )

    for keyword in _UNSUPPORTED_HARD_KEYWORDS:
        if keyword in schema:
            _add_issue(
                result,
                severity="error",
                code="ERR_SCHEMA_UNSUPPORTED_KEYWORD",
                path=f"$.{keyword}",
                message=f"Keyword '{keyword}' is not supported in Brimley v0.4 converter.",
            )

    required_fields = schema.get("required", []) or []
    if not isinstance(required_fields, list):
        _add_issue(
            result,
            severity="error",
            code="ERR_SCHEMA_REQUIRED_TYPE",
            path="$.required",
            message="Keyword 'required' must be an array of field names.",
        )
        return result

    properties = schema.get("properties", {}) or {}
    if not isinstance(properties, dict):
        _add_issue(
            result,
            severity="error",
            code="ERR_SCHEMA_PROPERTIES_TYPE",
            path="$.properties",
            message="Keyword 'properties' must be an object.",
        )
        return result

    additional_properties = schema.get("additionalProperties", False)
    if isinstance(additional_properties, dict):
        _add_issue(
            result,
            severity="error",
            code="ERR_SCHEMA_ADDITIONAL_PROPERTIES",
            path="$.additionalProperties",
            message="Object-valued additionalProperties is unsupported in Brimley v0.4.",
        )
    elif additional_properties is True:
        if allow_lossy:
            _add_issue(
                result,
                severity="warning",
                code="WARN_SCHEMA_ADDITIONAL_PROPERTIES_FLATTENED",
                path="$.additionalProperties",
                message="Permissive additionalProperties was dropped during lossy conversion.",
            )
        else:
            _add_issue(
                result,
                severity="error",
                code="ERR_SCHEMA_ADDITIONAL_PROPERTIES",
                path="$.additionalProperties",
                message="additionalProperties=true requires --allow-lossy for conversion.",
            )

    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            _add_issue(
                result,
                severity="error",
                code="ERR_SCHEMA_FIELD_TYPE",
                path=f"$.properties.{field_name}",
                message="Property definition must be an object.",
            )
            continue

        _handle_unknown_keys(
            result=result,
            location=f"$.properties.{field_name}",
            payload=field_schema,
            supported_keys=_SUPPORTED_PROPERTY_KEYS,
            allow_lossy=allow_lossy,
        )

        field_spec = _convert_property(
            result=result,
            field_name=field_name,
            field_schema=field_schema,
            required=field_name in required_fields,
        )
        if field_spec is not None:
            result.inline[field_name] = field_spec

    result.report.converted_fields = len(result.inline)
    return result


def _convert_property(
    result: SchemaConversionResult,
    field_name: str,
    field_schema: dict[str, Any],
    required: bool,
) -> dict[str, Any] | None:
    for keyword in _UNSUPPORTED_HARD_KEYWORDS:
        if keyword in field_schema:
            _add_issue(
                result,
                severity="error",
                code="ERR_SCHEMA_UNSUPPORTED_KEYWORD",
                path=f"$.properties.{field_name}.{keyword}",
                message=f"Keyword '{keyword}' is not supported in Brimley v0.4 converter.",
            )
            return None

    json_type = str(field_schema.get("type", "string"))
    brimley_type = _map_json_type_to_brimley_type(result, field_name, json_type, field_schema)
    if brimley_type is None:
        return None

    field_spec: dict[str, Any] = {"type": brimley_type}

    if "description" in field_schema:
        field_spec["description"] = field_schema["description"]
    if "default" in field_schema:
        field_spec["default"] = field_schema["default"]
    if "enum" in field_schema:
        field_spec["enum"] = field_schema["enum"]
    if "minimum" in field_schema:
        field_spec["min"] = field_schema["minimum"]
    if "maximum" in field_schema:
        field_spec["max"] = field_schema["maximum"]
    if "pattern" in field_schema:
        field_spec["pattern"] = field_schema["pattern"]

    if not required:
        field_spec["required"] = False

    return field_spec


def _map_json_type_to_brimley_type(
    result: SchemaConversionResult,
    field_name: str,
    json_type: str,
    field_schema: dict[str, Any],
) -> str | None:
    if json_type == "string":
        format_name = field_schema.get("format")
        if format_name == "date":
            return "date"
        if format_name == "date-time":
            return "datetime"
        return "string"

    if json_type == "integer":
        return "int"

    if json_type == "number":
        _add_issue(
            result,
            severity="warning",
            code="WARN_SCHEMA_NUMBER_TO_FLOAT",
            path=f"$.properties.{field_name}.type",
            message="JSON Schema 'number' mapped to Brimley 'float' (Tier 2 conversion).",
        )
        return "float"

    if json_type == "boolean":
        return "bool"

    if json_type == "array":
        items = field_schema.get("items")
        if not isinstance(items, dict):
            _add_issue(
                result,
                severity="error",
                code="ERR_SCHEMA_ARRAY_ITEMS",
                path=f"$.properties.{field_name}.items",
                message="Array 'items' must be an object with a supported primitive type.",
            )
            return None

        item_type = str(items.get("type", ""))
        item_brimley = _map_json_type_to_brimley_type(result, f"{field_name}[]", item_type, items)
        if item_brimley is None or item_brimley.endswith("[]"):
            _add_issue(
                result,
                severity="error",
                code="ERR_SCHEMA_ARRAY_NESTED",
                path=f"$.properties.{field_name}",
                message="Nested arrays are not supported in Brimley v0.4 converter.",
            )
            return None

        return f"{item_brimley}[]"

    _add_issue(
        result,
        severity="error",
        code="ERR_SCHEMA_UNSUPPORTED_TYPE",
        path=f"$.properties.{field_name}.type",
        message=f"Unsupported JSON Schema type '{json_type}' for Brimley v0.4 converter.",
    )
    return None


def _handle_unknown_keys(
    result: SchemaConversionResult,
    location: str,
    payload: dict[str, Any],
    supported_keys: set[str],
    allow_lossy: bool,
) -> None:
    for key in payload:
        if key in supported_keys or key in _UNSUPPORTED_HARD_KEYWORDS:
            continue

        if allow_lossy:
            _add_issue(
                result,
                severity="warning",
                code="WARN_SCHEMA_DROPPED_KEYWORD",
                path=f"{location}.{key}",
                message=f"Dropped unsupported keyword '{key}' during lossy conversion.",
            )
            continue

        _add_issue(
            result,
            severity="error",
            code="ERR_SCHEMA_UNSUPPORTED_KEYWORD",
            path=f"{location}.{key}",
            message=f"Unsupported keyword '{key}'. Re-run with --allow-lossy to drop it.",
        )


def _add_issue(
    result: SchemaConversionResult,
    severity: Literal["warning", "error"],
    code: str,
    path: str,
    message: str,
) -> None:
    result.report.issues.append(
        SchemaConversionIssue(
            severity=severity,
            code=code,
            path=path,
            message=message,
        )
    )
    if severity == "warning":
        result.report.warnings += 1
    else:
        result.report.errors += 1
