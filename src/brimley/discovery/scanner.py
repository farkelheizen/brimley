import os
import re
from pathlib import Path
from typing import List, Set, Optional
from pydantic import BaseModel, Field

from brimley.core.entity import Entity
from brimley.core.models import BrimleyFunction
from brimley.core.naming import (
    build_canonical_id,
    is_reserved_function_name,
    normalize_name_for_proximity,
)
from brimley.utils.diagnostics import BrimleyDiagnostic
from brimley.discovery.sql_parser import parse_sql_file
from brimley.discovery.template_parser import parse_template_file
from brimley.discovery.python_parser import parse_python_file

class BrimleyScanResult(BaseModel):
    functions: List[BrimleyFunction] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)
    diagnostics: List[BrimleyDiagnostic] = Field(default_factory=list)

class Scanner:
    """
    Scans a directory for Brimley functions and entities.
    """
    
    # Regex for valid function/entity names (starts with letter, alphanumeric/underscore/dash, max 64)
    NAME_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def scan(self) -> BrimleyScanResult:
        functions: List[BrimleyFunction] = []
        entities: List[Entity] = []
        diagnostics: List[BrimleyDiagnostic] = []
        seen_function_names: Set[str] = set()
        seen_entity_names: Set[str] = set()
        seen_identity_keys: Set[str] = set()
        seen_function_proximity: dict[str, str] = {}
        seen_entity_proximity: dict[str, str] = {}

        # Walk the directory
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                file_path = Path(root) / file
                
                # 1. Identification by extension/parser contract
                file_type = self._identify_file_type(file_path)
                if not file_type:
                    continue  # Silent ignore

                # 2. Parsing
                try:
                    parsed = self._parse_file(file_path, file_type)
                except ValueError as e:
                    # Parsing failed (e.g., bad YAML, missing fields)
                    diagnostics.append(BrimleyDiagnostic(
                        file_path=str(file_path),
                        error_code="ERR_PARSE_FAILURE",
                        message=str(e),
                        suggestion="Check YAML syntax and required fields."
                    ))
                    continue
                except Exception as e:
                    # Generic failure
                    diagnostics.append(BrimleyDiagnostic(
                        file_path=str(file_path),
                        error_code="ERR_INTERNAL",
                        message=f"Unexpected error: {e}",
                    ))
                    continue

                objects = parsed if isinstance(parsed, list) else [parsed]

                for obj in objects:
                    if not obj.name or not self.NAME_REGEX.match(obj.name):
                        diagnostics.append(BrimleyDiagnostic(
                            file_path=str(file_path),
                            error_code="ERR_INVALID_NAME",
                            message=f"'{obj.name}' is an invalid name.",
                            suggestion="Names must start with a letter and contain only alphanumeric chars, underscores, or dashes.",
                            line_number=None
                        ))
                        continue

                    if isinstance(obj, BrimleyFunction) and is_reserved_function_name(obj.name):
                        diagnostics.append(BrimleyDiagnostic(
                            file_path=str(file_path),
                            error_code="ERR_RESERVED_NAME",
                            message=f"Function name '{obj.name}' is reserved.",
                            suggestion="Rename the function to avoid REPL/admin command collisions.",
                            line_number=None,
                        ))
                        continue

                    kind = "function" if isinstance(obj, BrimleyFunction) else "entity"
                    symbol = obj.name
                    if isinstance(obj, BrimleyFunction) and getattr(obj, "handler", None):
                        handler_value = getattr(obj, "handler")
                        if isinstance(handler_value, str) and "." in handler_value:
                            symbol = handler_value.rsplit(".", 1)[-1]

                    canonical_id = build_canonical_id(
                        kind=kind,
                        root_dir=self.root_dir,
                        source_file=file_path,
                        symbol=symbol,
                    )
                    identity_key = canonical_id.lower()
                    if identity_key in seen_identity_keys:
                        diagnostics.append(BrimleyDiagnostic(
                            file_path=str(file_path),
                            error_code="ERR_IDENTITY_COLLISION",
                            message=f"Canonical identity collision for '{obj.name}' ({canonical_id}).",
                            suggestion="Rename the symbol or move one definition to a unique source path.",
                            line_number=None,
                        ))
                        continue
                    seen_identity_keys.add(identity_key)
                    if hasattr(obj, "canonical_id"):
                        obj.canonical_id = canonical_id

                    proximity_key = normalize_name_for_proximity(obj.name)
                    proximity_map = seen_function_proximity if isinstance(obj, BrimleyFunction) else seen_entity_proximity
                    existing_similar = proximity_map.get(proximity_key)
                    if existing_similar and existing_similar != obj.name:
                        diagnostics.append(BrimleyDiagnostic(
                            file_path=str(file_path),
                            error_code="ERR_NAME_PROXIMITY",
                            message=(
                                f"Name '{obj.name}' is very similar to '{existing_similar}'. "
                                "This may confuse operators and clients."
                            ),
                            severity="warning",
                            suggestion="Prefer a more distinct identifier to reduce ambiguity.",
                            line_number=None,
                        ))
                    else:
                        proximity_map[proximity_key] = obj.name

                    if isinstance(obj, BrimleyFunction):
                        if obj.name in seen_function_names:
                            diagnostics.append(BrimleyDiagnostic(
                                file_path=str(file_path),
                                error_code="ERR_DUPLICATE_NAME",
                                message=f"Function '{obj.name}' is already defined.",
                                suggestion="Rename this function or removed the duplicate."
                            ))
                            continue
                        seen_function_names.add(obj.name)
                        functions.append(obj)
                    else:
                        if obj.name in seen_entity_names:
                            diagnostics.append(BrimleyDiagnostic(
                                file_path=str(file_path),
                                error_code="ERR_DUPLICATE_NAME",
                                message=f"Entity '{obj.name}' is already defined.",
                                suggestion="Rename this entity or removed the duplicate."
                            ))
                            continue
                        seen_entity_names.add(obj.name)
                        entities.append(obj)

        return BrimleyScanResult(functions=functions, entities=entities, diagnostics=diagnostics)

    def _identify_file_type(self, file_path: Path) -> Optional[str]:
        """
        Identify parser route by file extension and frontmatter markers.
        """
        suffix = file_path.suffix.lower()

        if suffix == ".py":
            return "python_function"

        if suffix == ".sql":
            if self._has_sql_frontmatter(file_path):
                return "sql_function"
            return None

        if suffix == ".md":
            if self._has_markdown_frontmatter(file_path):
                return "template_function"
            return None

        # YAML entities are removed from scanner routing in decorator transition.
        return None

    def _has_markdown_frontmatter(self, file_path: Path) -> bool:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return False

        stripped = content.lstrip()
        return stripped.startswith("---")

    def _has_sql_frontmatter(self, file_path: Path) -> bool:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return False

        stripped = content.lstrip()
        return stripped.startswith("/*") and "---" in stripped

    def _parse_file(self, file_path: Path, file_type: str) -> Entity:
        """
        Delegates to specific parsers based on type/extension.
        """
        if file_type == "sql_function":
            return parse_sql_file(file_path)
        elif file_type == "template_function":
            return parse_template_file(file_path)
        elif file_type == "python_function":
            return parse_python_file(file_path)
        else:
            raise ValueError(f"Unknown file type: {file_type}")
