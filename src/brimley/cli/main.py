import typer
import yaml
import json
import sys
from pathlib import Path
from typing import Optional, Annotated 
# from typing_extensions import Annotated # Use standard library

from brimley.core.context import BrimleyContext
from brimley.discovery.scanner import Scanner
from brimley.core.registry import Registry
from brimley.execution.dispatcher import Dispatcher
from brimley.execution.arguments import ArgumentResolver

app = typer.Typer(name="brimley", help="Brimley CLI Interface")

@app.command()
def invoke(
    names: Annotated[list[str], typer.Argument(help="Name of the function to execute")],
    root_dir: Annotated[Path, typer.Option("--root", "-r", help="Root directory to scan")] = Path("."),
    input_data: Annotated[str, typer.Option("--input", "-i", help="Input JSON/YAML string or file path")] = "{}"
):
    """
    Invoke a Brimley function by name.
    """
    if not names:
        typer.echo("Error: Missing function name.", err=True)
        raise typer.Exit(code=2)

    # Workaround for argument shifting issue
    if len(names) > 1 and names[0] == "invoke":
        names.pop(0)

    function_name = names[0]
    # ... rest ...
    # 1. Load Context & Resources
    root_path = Path(root_dir)
    context = BrimleyContext()
    
    # 2. Scan & Register
    # Use stderr for system logs
    if root_path.exists():
        scanner = Scanner(root_path)
        scan_result = scanner.scan()
    else:
        typer.echo(f"[SYSTEM] Warning: Root directory '{root_dir}' does not exist.", err=True)
        from brimley.discovery.scanner import BrimleyScanResult
        scan_result = BrimleyScanResult()

    # Log Diagnostics
    if scan_result.diagnostics:
        typer.echo(f"[SYSTEM] Encountered {len(scan_result.diagnostics)} diagnostics:", err=True)
        for err in scan_result.diagnostics:
            typer.echo(f"  - [{err.severity}] {err.message} ({err.file_path})", err=True)
            
    failed = [d for d in scan_result.diagnostics if d.severity in ("critical", "error")]
    if failed:
         typer.echo(f"[SYSTEM] Scan failed with {len(failed)} errors.", err=True)
    
    registry = Registry()
    registry.register_all(scan_result.functions)

    # 3. Lookup Function
    try:
        func = registry.get(function_name)
    except KeyError:
        # Retry logic or better error
        typer.echo(f"Error: Function '{function_name}' not found.", err=True)
        typer.echo(f"Available: {list(registry._functions.keys())}", err=True)
        raise typer.Exit(code=1)

    # 4. Parse Input
    parsed_input = {}
    if input_data and input_data.strip():
        # Check if it is a file
        p = Path(input_data)
        # If the string is likely a path and exists
        if len(input_data) < 256 and p.exists() and p.is_file():
            content = p.read_text()
        else:
            content = input_data
            
        try:
            parsed_input = yaml.safe_load(content)
            if parsed_input is None:
                parsed_input = {}
            elif not isinstance(parsed_input, dict):
                 typer.echo(f"Error: Input must resolve to a dictionary argument map.", err=True)
                 raise typer.Exit(code=1)
        except yaml.YAMLError as e:
            typer.echo(f"Error: Invalid YAML format in input: {e}", err=True)
            raise typer.Exit(code=1)

    # 5. Resolve Arguments
    try:
        resolved_args = ArgumentResolver.resolve(func, parsed_input, context)
    except Exception as e:
        typer.echo(f"Error Resolving Arguments: {e}", err=True)
        raise typer.Exit(code=1)

    # 6. Execute
    dispatcher = Dispatcher()
    try:
        result = dispatcher.run(func, resolved_args, context)
    except Exception as e:
        # In case of python errors, we might want traceback?
        # For CLI, just print error for now.
        typer.echo(f"Execution Error: {e}", err=True)
        raise typer.Exit(code=1)

    # 7. Output
    # If result is simple string (template), print raw
    if isinstance(result, str):
        print(result)
    else:
        # Dump JSON
        print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    app()
