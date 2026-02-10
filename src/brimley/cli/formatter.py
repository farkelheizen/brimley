import json
import typer
from typing import Any, List, Dict, Union
from pydantic import BaseModel

class OutputFormatter:
    """
    Handles output formatting for CLI and REPL.
    Ensures separation of concerns between System Logs (stderr) and Data (stdout).
    """
    
    @staticmethod
    def log(message: str, severity: str = "info") -> None:
        """
        Print system messages to stderr with color coding.
        """
        color = typer.colors.WHITE
        prefix = "[SYSTEM]"
        
        if severity == "warning":
            color = typer.colors.YELLOW
        elif severity == "error":
            color = typer.colors.RED
        elif severity == "success":
            color = typer.colors.GREEN
            
        typer.secho(f"{prefix} {message}", err=True, fg=color)

    @staticmethod
    def print_data(data: Any) -> None:
        """
        Print execution result to stdout. 
        Handles Pydantic models and complex types.
        """
        # 1. Raw Strings (Templates)
        if isinstance(data, str):
            typer.echo(data)
            return

        # 2. Serialize complex objects
        def json_serializer(obj):
            if isinstance(obj, BaseModel):
                return obj.model_dump(mode='json')
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return str(obj)

        # 3. Print JSON
        try:
            output = json.dumps(data, indent=2, default=json_serializer)
            typer.echo(output)
        except TypeError as e:
            OutputFormatter.log(f"JSON Serialization failed: {e}", severity="error")
            typer.echo(str(data))
