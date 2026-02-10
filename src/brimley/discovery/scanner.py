import os
import re
from pathlib import Path
from typing import List, Set, Optional
from pydantic import BaseModel, Field, ValidationError

from brimley.core.models import BrimleyFunction
from brimley.utils.diagnostics import BrimleyDiagnostic
from brimley.discovery.sql_parser import parse_sql_file
from brimley.discovery.template_parser import parse_template_file
from brimley.discovery.python_parser import parse_python_file

class BrimleyScanResult(BaseModel):
    functions: List[BrimleyFunction] = Field(default_factory=list)
    diagnostics: List[BrimleyDiagnostic] = Field(default_factory=list)

class Scanner:
    """
    Scans a directory for Brimley functions.
    """
    
    # Regex for valid function names (starts with letter, alphanumeric/underscore/dash, max 64)
    NAME_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def scan(self) -> BrimleyScanResult:
        functions: List[BrimleyFunction] = []
        diagnostics: List[BrimleyDiagnostic] = []
        seen_names: Set[str] = set()

        # Walk the directory
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                file_path = Path(root) / file
                
                # 1. Identification (500-char rule)
                func_type = self._identify_function_type(file_path)
                if not func_type:
                    continue  # Silent ignore

                # 2. Parsing
                try:
                    func = self._parse_file(file_path, func_type)
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

                # 3. Validation
                
                # Name validation check
                if not self.NAME_REGEX.match(func.name):
                    diagnostics.append(BrimleyDiagnostic(
                        file_path=str(file_path),
                        error_code="ERR_INVALID_NAME",
                        message=f"'{func.name}' is an invalid function name.",
                        suggestion="Names must start with a letter and contain only alphanumeric chars, underscores, or dashes.",
                        line_number=None 
                    ))
                    continue

                # Duplicate check
                if func.name in seen_names:
                    diagnostics.append(BrimleyDiagnostic(
                        file_path=str(file_path),
                        error_code="ERR_DUPLICATE_NAME",
                        message=f"Function '{func.name}' is already defined.",
                        suggestion="Rename this function or removed the duplicate."
                    ))
                    continue
                
                # Success
                seen_names.add(func.name)
                functions.append(func)

        return BrimleyScanResult(functions=functions, diagnostics=diagnostics)

    def _identify_function_type(self, file_path: Path) -> Optional[str]:
        """
        Reads first 500 chars to find 'type: ..._function'.
        """
        try:
            # Only checking specific extensions to avoid binary reads on images etc if mixed
            if file_path.suffix not in ['.py', '.sql', '.md', '.yaml', '.yml']:
                return None

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(500)
            
            # Simple regex to find type definition in YAML-like structure
            # Matches "type:[space]some_function"
            match = re.search(r'type:\s*([a-z_]+_function)', head)
            if match:
                return match.group(1)
        except Exception:
            return None
        return None

    def _parse_file(self, file_path: Path, func_type: str) -> BrimleyFunction:
        """
        Delegates to specific parsers based on type/extension.
        """
        if func_type == "sql_function":
            return parse_sql_file(file_path)
        elif func_type == "template_function":
            return parse_template_file(file_path)
        elif func_type == "python_function":
            return parse_python_file(file_path)
        else:
            raise ValueError(f"Unknown function type: {func_type}")
