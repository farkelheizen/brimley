import json
import typer
from typing import Any, List, Dict, Union
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from brimley.core.context import RuntimeErrorRecord
from brimley.utils.diagnostics import BrimleyDiagnostic

# Create a stderr console for logging
error_console = Console(stderr=True)

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
        style = "white"
        prefix = "[SYSTEM]"
        
        if severity == "warning":
            style = "yellow"
        elif severity == "error":
            style = "red"
        elif severity == "critical":
            style = "bold red"
        elif severity == "success":
            style = "green"
            
        error_console.print(f"[{style}]{prefix} {message}[/{style}]")

    @staticmethod
    def print_diagnostics(diagnostics: List[BrimleyDiagnostic]) -> None:
        """
        Prints a 'Wall of Shame' table for diagnostics.
        """
        if not diagnostics:
            return

        table = Table(title="Brimley Diagnostics", border_style="red", header_style="bold red")
        table.add_column("Severity", style="bold")
        table.add_column("Code")
        table.add_column("Message")
        table.add_column("Location")
        
        for diag in diagnostics:
            color = "red"
            if diag.severity == "warning":
                color = "yellow"
            elif diag.severity == "critical":
                color = "bold red"
                
            loc = f"{diag.file_path}"
            if diag.line_number:
                loc += f":{diag.line_number}"
                
            table.add_row(
                f"[{color}]{diag.severity.upper()}[/{color}]",
                diag.error_code,
                diag.message,
                loc
            )
            
        error_console.print(table)
        error_console.print() # spacing

    @staticmethod
    def print_runtime_errors(
        records: List[RuntimeErrorRecord],
        total: int,
        limit: int,
        offset: int,
        include_history: bool,
    ) -> None:
        """Print persisted runtime errors for REPL `/errors` output."""
        if not records:
            return

        title = "Brimley Runtime Errors"
        if include_history:
            title = "Brimley Runtime Errors (Including History)"

        table = Table(title=title, border_style="red", header_style="bold red")
        table.add_column("Severity", style="bold")
        table.add_column("Error Class")
        table.add_column("Message")
        table.add_column("Object")
        table.add_column("Location")
        table.add_column("Status")

        for record in records:
            color = "red"
            if record.severity == "warning":
                color = "yellow"
            elif record.severity == "critical":
                color = "bold red"

            location = record.file_path
            if record.line_number is not None:
                location = f"{location}:{record.line_number}"

            table.add_row(
                f"[{color}]{record.severity.upper()}[/{color}]",
                record.error_class,
                record.message,
                record.object_name,
                location,
                record.status,
            )

        error_console.print(table)
        shown = len(records)
        error_console.print(f"Showing {shown} of {total} runtime errors (offset={offset}, limit={limit}).")
        error_console.print()

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
