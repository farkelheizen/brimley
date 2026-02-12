from typing import Optional
from pydantic import BaseModel

class BrimleyDiagnostic(BaseModel):
    """
    Standardized error reporting object for discovery and registration issues.
    """
    file_path: str
    error_code: str
    message: str
    severity: str = "error" # 'error', 'warning', 'critical'
    suggestion: Optional[str] = None
    line_number: Optional[int] = None

    def __str__(self) -> str:
        loc = f"{self.file_path}"
        if self.line_number:
            loc += f":{self.line_number}"
        return f"[{self.error_code}] {self.message} (at {loc})"

class BrimleyExecutionError(Exception):
    """
    Exception raised during function execution, providing context about 
    validation failures or runtime issues.
    """
    def __init__(self, message: str, func_name: str = None):
        self.message = message
        self.func_name = func_name
        ctx = f" in function '{func_name}'" if func_name else ""
        super().__init__(f"Execution Error{ctx}: {message}")
