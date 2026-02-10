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
from brimley.cli.formatter import OutputFormatter
from brimley.cli.repl import BrimleyREPL

app = typer.Typer(name="brimley", help="Brimley CLI Interface")

@app.command()
def repl(
    root_dir: Annotated[Path, typer.Option("--root", "-r", help="Root directory to scan")] = Path("."),
):
    """
    Start an interactive REPL session.
    """
    repl_session = BrimleyREPL(root_dir)
    repl_session.start()

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
    if root_path.exists():
        scanner = Scanner(root_path)
        scan_result = scanner.scan()
    else:
        OutputFormatter.log(f"Warning: Root directory '{root_dir}' does not exist.", severity="warning")
        from brimley.discovery.scanner import BrimleyScanResult
        scan_result = BrimleyScanResult()

    # Log Diagnostics
    if scan_result.diagnostics:
        OutputFormatter.log(f"Encountered {len(scan_result.diagnostics)} diagnostics:", severity="warning")
        for err in scan_result.diagnostics:
            OutputFormatter.log(f"- {err.message} ({err.file_path})", severity=err.severity)
            
    failed = [d for d in scan_result.diagnostics if d.severity in ("critical", "error")]
    if failed:
         OutputFormatter.log(f"Scan failed with {len(failed)} errors.", severity="error")
    
    registry = Registry()
    registry.register_all(scan_result.functions)

    # 3. Lookup Function
    try:
        func = registry.get(function_name)
    except KeyError:
        OutputFormatter.log(f"Error: Function '{function_name}' not found.", severity="error")
        OutputFormatter.log(f"Available: {list(registry._functions.keys())}", severity="info")
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
                 OutputFormatter.log("Error: Input must resolve to a dictionary argument map.", severity="error")
                 raise typer.Exit(code=1)
        except yaml.YAMLError as e:
            OutputFormatter.log(f"Error: Invalid YAML format in input: {e}", severity="error")
            raise typer.Exit(code=1)

    # 5. Resolve Arguments
    try:
        resolved_args = ArgumentResolver.resolve(func, parsed_input, context)
    except Exception as e:
        OutputFormatter.log(f"Error Resolving Arguments: {e}", severity="error")
        raise typer.Exit(code=1)

    # 6. Execute
    dispatcher = Dispatcher()
    try:
        result = dispatcher.run(func, resolved_args, context)
    except Exception as e:
        OutputFormatter.log(f"Execution Error: {e}", severity="error")
        raise typer.Exit(code=1)

    # 7. Output
    OutputFormatter.print_data(result)

if __name__ == "__main__":
    app()
