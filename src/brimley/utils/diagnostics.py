from typing import Optional
from pydantic import BaseModel

class BrimleyDiagnostic(BaseModel):
    """
    Standardized error reporting object for discovery and registration issues.
    """
    file_path: str
    error_code: str
    message: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None

    def __str__(self) -> str:
        loc = f"{self.file_path}"
        if self.line_number:
            loc += f":{self.line_number}"
        return f"[{self.error_code}] {self.message} (at {loc})"
