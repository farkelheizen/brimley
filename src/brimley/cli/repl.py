import typer
import yaml
import shlex
import json
from pathlib import Path
from typing import Optional
import sys
from prompt_toolkit import PromptSession

from brimley.core.context import BrimleyContext
from brimley.config.loader import load_config
from brimley.infrastructure.database import initialize_databases
from brimley.discovery.scanner import Scanner, BrimleyScanResult
from brimley.core.registry import Registry
from brimley.execution.dispatcher import Dispatcher
from brimley.execution.arguments import ArgumentResolver
from brimley.cli.formatter import OutputFormatter

class BrimleyREPL:
    def __init__(self, root_dir: Path, mcp_enabled_override: Optional[bool] = None):
        self.root_dir = root_dir
        self.mcp_enabled_override = mcp_enabled_override
        
        # Load config: check root_dir first, then CWD
        config_path = self.root_dir / "brimley.yaml"
        if not config_path.exists():
            config_path = Path.cwd() / "brimley.yaml"
            
        config_data = load_config(config_path)
        self.context = BrimleyContext(config_dict=config_data)

        # CLI override takes precedence over config/default
        self.mcp_embedded_enabled = (
            self.mcp_enabled_override if self.mcp_enabled_override is not None else self.context.mcp.embedded
        )
        
        # Hydrate databases
        if self.context.databases:
            self.context.databases = initialize_databases(self.context.databases)
        
        self.dispatcher = Dispatcher()
        self.prompt_session = PromptSession()

    def load(self):
        """
        Scans directory and populates registry.
        """
        if self.root_dir.exists():
            OutputFormatter.log(f"Scanning {self.root_dir}...", severity="info")
            scanner = Scanner(self.root_dir)
            scan_result = scanner.scan()
        else:
            OutputFormatter.log(f"Warning: Root directory '{self.root_dir}' does not exist.", severity="warning")
            scan_result = BrimleyScanResult()

        if scan_result.diagnostics:
             OutputFormatter.print_diagnostics(scan_result.diagnostics)

        # Register everything into context
        self.context.functions.register_all(scan_result.functions)
        self.context.entities.register_all(scan_result.entities)
        
        func_names = [f.name for f in self.context.functions]
        OutputFormatter.log(f"Loaded {len(self.context.functions)} functions: {', '.join(func_names)}", severity="success")
        OutputFormatter.log(f"Loaded {len(scan_result.entities)} entities.", severity="success")

    def start(self):
        OutputFormatter.log("Brimley REPL. Type '/help' for admin commands or '/quit' to exit.", severity="info")
        self.load()

        while True:
            try:
                if sys.stdin.isatty():
                    command_line = self.prompt_session.prompt("brimley > ")
                else:
                    command_line = typer.prompt("brimley >", prompt_suffix=" ", default="", show_default=False)
                
                if not command_line:
                    continue
                    
                command_line = command_line.strip()
                
                # Admin Commands
                if command_line.startswith('/'):
                    should_continue = self.handle_admin_command(command_line)
                    if not should_continue:
                        break
                    continue

                # Legacy/Direct exit
                if command_line in ("exit", "quit"):
                    OutputFormatter.log("Exiting Brimley REPL.", severity="info")
                    break
                    
                if command_line == "reset":
                    OutputFormatter.log("Reloading...", severity="info")
                    # Reload config when resetting
                    config_path = Path.cwd() / "brimley.yaml"
                    config_data = load_config(config_path)
                    self.context = BrimleyContext(config_dict=config_data)

                    # Keep CLI override precedence after reset
                    self.mcp_embedded_enabled = (
                        self.mcp_enabled_override
                        if self.mcp_enabled_override is not None
                        else self.context.mcp.embedded
                    )
                    
                    # Hydrate databases
                    if self.context.databases:
                        self.context.databases = initialize_databases(self.context.databases)
                        
                    self.load()
                    OutputFormatter.log("Rescan complete.", severity="success")
                    continue

                self.handle_command(command_line)

            except (KeyboardInterrupt, EOFError):
                 OutputFormatter.log("\nExiting...", severity="info")
                 break
            except Exception as e:
                OutputFormatter.log(f"System Error: {e}", severity="critical")

    def handle_admin_command(self, line: str) -> bool:
        """
        Processes commands starting with '/'.
        Returns False to signal REPL exit, True to continue.
        """
        parts = line[1:].split()
        if not parts:
            return True
        
        cmd = parts[0].lower()
        args = parts[1:]

        handlers = {
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "help": self._cmd_help,
            "settings": self._cmd_settings,
            "config": self._cmd_config,
            "state": self._cmd_state,
            "functions": self._cmd_functions,
            "entities": self._cmd_entities,
            "databases": self._cmd_databases,
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(args)
        else:
            OutputFormatter.log(f"Unknown admin command: /{cmd}. Type /help for options.", severity="error")
            return True

    def _cmd_quit(self, args) -> bool:
        OutputFormatter.log("Exiting Brimley REPL.", severity="info")
        return False

    def _cmd_help(self, args) -> bool:
        commands = [
            ("/settings", "Dumps internal framework configuration (read-only)."),
            ("/config", "Dumps user application configuration (read-only)."),
            ("/state", "Dumps current mutable application state."),
            ("/functions", "Lists all registered functions and their types."),
            ("/entities", "Lists all registered entities."),
            ("/databases", "Lists configured database connections."),
            ("/help", "Lists available admin commands."),
            ("/quit", "Exits the REPL."),
        ]
        OutputFormatter.log("\nAvailable Admin Commands:", severity="info")
        for cmd, desc in commands:
            typer.echo(f"  {cmd:<12} {desc}")
        typer.echo("")
        return True

    def _cmd_settings(self, args) -> bool:
        typer.echo(self.context.settings.model_dump_json(indent=2))
        return True

    def _cmd_config(self, args) -> bool:
        typer.echo(self.context.config.model_dump_json(indent=2))
        return True

    def _cmd_state(self, args) -> bool:
        typer.echo(json.dumps(self.context.app, indent=2, default=str))
        return True

    def _cmd_functions(self, args) -> bool:
        if not self.context.functions:
            OutputFormatter.log("No functions registered.", severity="info")
            return True
        
        OutputFormatter.log(f"Registered Functions ({len(self.context.functions)}):", severity="info")
        # Registry items are BrimleyFunction objects (which have name and type)
        for func in self.context.functions:
            typer.echo(f"  [{func.type}] {func.name}")
        return True

    def _cmd_entities(self, args) -> bool:
        if not self.context.entities:
            OutputFormatter.log("No entities registered.", severity="info")
            return True
        
        OutputFormatter.log(f"Registered Entities ({len(self.context.entities)}):", severity="info")
        for entity in self.context.entities:
            # entities registry stores classes or items with .name
            name = getattr(entity, "name", entity.__class__.__name__)
            typer.echo(f"  {name}")
        return True

    def _cmd_databases(self, args) -> bool:
        if not self.context.databases:
            OutputFormatter.log("No database connections configured.", severity="info")
            return True
        
        OutputFormatter.log("Database Configurations:", severity="info")
        typer.echo(json.dumps(self.context.databases, indent=2, default=str))
        return True

    def handle_command(self, line: str):
        # Format: [NAME] [ARGS...]
        parts = line.split(" ", 1)
        func_name = parts[0]
        arg_str = parts[1] if len(parts) > 1 else None

        if func_name not in self.context.functions:
            OutputFormatter.log(f"Function '{func_name}' not found.", severity="error")
            return

        func = self.context.functions.get(func_name)
        input_content = "{}"

        # 1. Multi-line Input
        if arg_str is None:
            OutputFormatter.log("** Enter multi-line input (finish with empty line) **", severity="info")
            lines = []
            while True:
                try:
                    if sys.stdin.isatty():
                        part = self.prompt_session.prompt("")
                    else:
                        part = typer.prompt("", default="", show_default=False)
                    if not part:
                        break
                    lines.append(part)
                except (EOFError, KeyboardInterrupt):
                    break
            input_content = "\n".join(lines)
            if not input_content.strip():
                input_content = "{}"
        
        # 2. File Input (@filename)
        elif arg_str.startswith("@"):
            file_path = Path(arg_str[1:].strip())
            if not file_path.exists():
                OutputFormatter.log(f"Error: Input file '{file_path}' not found.", severity="error")
                return
            try:
                input_content = file_path.read_text()
            except Exception as e:
                OutputFormatter.log(f"Error reading file {file_path}: {e}", severity="error")
                return
        
        # 3. Inline Input
        else:
            input_content = arg_str

        # Parse args
        try:
            parsed_input = yaml.safe_load(input_content)
            if parsed_input is None:
                parsed_input = {}
            if not isinstance(parsed_input, dict):
                 OutputFormatter.log("Input args must appear as a dict/map.", severity="error")
                 return
        except yaml.YAMLError as e:
            OutputFormatter.log(f"Invalid argument syntax: {e}", severity="error")
            return

        # Execute
        try:
            OutputFormatter.log(f"Executing '{func_name}'...", severity="info")
            resolved_args = ArgumentResolver.resolve(func, parsed_input, self.context)
            result = self.dispatcher.run(func, resolved_args, self.context)
            OutputFormatter.print_data(result)
        except Exception as e:
            OutputFormatter.log(f"Execution failed: {e}", severity="error")
