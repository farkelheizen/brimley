import typer
import yaml
import json
import sys
from pathlib import Path
from typing import Optional, Annotated 
# from typing_extensions import Annotated # Use standard library

from brimley.core.context import BrimleyContext
from brimley.config.loader import load_config
from brimley.infrastructure.database import initialize_databases
from brimley.discovery.scanner import Scanner
from brimley.core.registry import Registry
from brimley.execution.dispatcher import Dispatcher
from brimley.execution.arguments import ArgumentResolver
from brimley.cli.formatter import OutputFormatter
from brimley.cli.repl import BrimleyREPL
from brimley.mcp.adapter import BrimleyMCPAdapter

app = typer.Typer(name="brimley", help="Brimley CLI Interface")


def _resolve_optional_bool_flag(enabled: bool, disabled: bool, flag_name: str) -> Optional[bool]:
    if enabled and disabled:
        raise typer.BadParameter(f"Cannot use --{flag_name} and --no-{flag_name} together.")
    if enabled:
        return True
    if disabled:
        return False
    return None

@app.command()
def repl(
    root_dir: Annotated[Path, typer.Option("--root", "-r", help="Root directory to scan")] = Path("."),
    mcp: Annotated[bool, typer.Option("--mcp", help="Enable embedded MCP server for REPL")] = False,
    no_mcp: Annotated[bool, typer.Option("--no-mcp", help="Disable embedded MCP server for REPL")] = False,
    watch: Annotated[bool, typer.Option("--watch", help="Enable auto-reload watch mode for REPL")] = False,
    no_watch: Annotated[bool, typer.Option("--no-watch", help="Disable auto-reload watch mode for REPL")] = False,
):
    """
    Start an interactive REPL session.
    """
    mcp_enabled_override = _resolve_optional_bool_flag(mcp, no_mcp, "mcp")
    auto_reload_enabled_override = _resolve_optional_bool_flag(watch, no_watch, "watch")
    repl_session = BrimleyREPL(
        root_dir,
        mcp_enabled_override=mcp_enabled_override,
        auto_reload_enabled_override=auto_reload_enabled_override,
    )
    repl_session.start()


@app.command("mcp-serve")
def mcp_serve(
    root_dir: Annotated[Path, typer.Option("--root", "-r", help="Root directory to scan")] = Path("."),
    watch: Annotated[bool, typer.Option("--watch", help="Enable auto-reload watch mode for MCP server")] = False,
    no_watch: Annotated[bool, typer.Option("--no-watch", help="Disable auto-reload watch mode for MCP server")] = False,
    host: Annotated[Optional[str], typer.Option("--host", help="Override MCP host bind address")] = None,
    port: Annotated[Optional[int], typer.Option("--port", min=1, max=65535, help="Override MCP port")] = None,
):
    """
    Start a non-REPL MCP server.
    """
    watch_override = _resolve_optional_bool_flag(watch, no_watch, "watch")

    config_path = root_dir / "brimley.yaml"
    if not config_path.exists():
        config_path = Path.cwd() / "brimley.yaml"

    context = BrimleyContext(config_dict=load_config(config_path))

    effective_watch = watch_override if watch_override is not None else context.auto_reload.enabled
    effective_host = host if host is not None else context.mcp.host
    effective_port = port if port is not None else context.mcp.port

    if root_dir.exists():
        scanner = Scanner(root_dir)
        scan_result = scanner.scan()
    else:
        OutputFormatter.log(f"Warning: Root directory '{root_dir}' does not exist.", severity="warning")
        from brimley.discovery.scanner import BrimleyScanResult
        scan_result = BrimleyScanResult()

    if scan_result.diagnostics:
        OutputFormatter.print_diagnostics(scan_result.diagnostics)

    context.functions.register_all(scan_result.functions)
    context.entities.register_all(scan_result.entities)

    adapter = BrimleyMCPAdapter(registry=context.functions, context=context)
    tools = adapter.discover_tools()
    if not tools:
        OutputFormatter.log("No MCP tools discovered. Nothing to serve.", severity="warning")
        raise typer.Exit(code=0)

    if effective_watch:
        OutputFormatter.log("Watch mode for mcp-serve is planned for AR-P8-S3; running without watcher.", severity="warning")

    try:
        mcp_server = adapter.register_tools()
    except RuntimeError as exc:
        OutputFormatter.log(str(exc), severity="error")
        raise typer.Exit(code=1)
    except Exception as exc:
        OutputFormatter.log(f"Unable to initialize MCP server: {exc}", severity="error")
        raise typer.Exit(code=1)

    if mcp_server is None or not hasattr(mcp_server, "run"):
        OutputFormatter.log("Unable to start MCP server: no runnable server instance was created.", severity="error")
        raise typer.Exit(code=1)

    OutputFormatter.log(
        f"Serving Brimley MCP tools at http://{effective_host}:{effective_port}/sse",
        severity="success",
    )
    mcp_server.run(transport="sse", host=effective_host, port=effective_port)

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

    # 1. Load Context & Resources
    root_path = Path(root_dir)
    config_path = root_path / "brimley.yaml"
    if not config_path.exists():
        config_path = Path.cwd() / "brimley.yaml"
        
    config_data = load_config(config_path)
    context = BrimleyContext(config_dict=config_data)

    # Hydrate databases
    if context.databases:
        context.databases = initialize_databases(context.databases)
    
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
        OutputFormatter.print_diagnostics(scan_result.diagnostics)
            
    failed = [d for d in scan_result.diagnostics if d.severity in ("critical", "error")]
    if failed:
         OutputFormatter.log(f"Scan failed with {len(failed)} errors.", severity="error")
    
    # Register everything into context
    context.functions.register_all(scan_result.functions)
    context.entities.register_all(scan_result.entities)

    # 3. Lookup Function
    try:
        func = context.functions.get(function_name)
    except KeyError:
        OutputFormatter.log(f"Error: Function '{function_name}' not found.", severity="error")
        # Accessing internal _items for logging is okay, but list(context.functions) also works
        available = [f.name for f in context.functions]
        OutputFormatter.log(f"Available: {available}", severity="info")
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
