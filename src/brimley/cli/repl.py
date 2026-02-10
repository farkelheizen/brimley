import typer
import yaml
import shlex
from pathlib import Path
from typing import Optional

from brimley.core.context import BrimleyContext
from brimley.discovery.scanner import Scanner, BrimleyScanResult
from brimley.core.registry import Registry
from brimley.execution.dispatcher import Dispatcher
from brimley.execution.arguments import ArgumentResolver
from brimley.cli.formatter import OutputFormatter

class BrimleyREPL:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.context = BrimleyContext()
        self.registry = Registry()
        self.dispatcher = Dispatcher()

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
             OutputFormatter.log(f"Encountered {len(scan_result.diagnostics)} diagnostics.", severity="warning")
             # Print diagnostics?

        self.registry = Registry()
        self.registry.register_all(scan_result.functions)
        OutputFormatter.log(f"Loaded {len(self.registry)} functions: {', '.join(self.registry._functions.keys())}", severity="success")

    def start(self):
        OutputFormatter.log("Brimley REPL. Type 'exit' to quit.", severity="info")
        self.load()

        while True:
            try:
                # Use typer.prompt for clean input handling or generic input()
                # We use simple input() to allow raw string typing.
                # using click.prompt allows validation, but we want a shell feel.
                command_line = typer.prompt("brimley >", prompt_suffix=" ", default="", show_default=False)
                
                if not command_line:
                    continue
                    
                command_line = command_line.strip()
                
                if command_line in ("exit", "quit"):
                    OutputFormatter.log("Exiting Brimley REPL.", severity="info")
                    break
                    
                if command_line == "reset":
                    OutputFormatter.log("Reloading...", severity="info")
                    self.context = BrimleyContext() # Reset context state
                    self.load()
                    OutputFormatter.log("Rescan complete.", severity="success")
                    continue

                self.handle_command(command_line)

            except (KeyboardInterrupt, EOFError):
                 OutputFormatter.log("\nExiting...", severity="info")
                 break
            except Exception as e:
                OutputFormatter.log(f"System Error: {e}", severity="critical")

    def handle_command(self, line: str):
        # Format: [NAME] [ARGS...]
        # Simple split on first space
        parts = line.split(" ", 1)
        func_name = parts[0]
        arg_str = parts[1] if len(parts) > 1 else "{}"

        if func_name not in self.registry:
            OutputFormatter.log(f"Function '{func_name}' not found.", severity="error")
            return

        func = self.registry.get(func_name)

        # Parse args
        try:
            # We assume inline YAML/JSON for now
            parsed_input = yaml.safe_load(arg_str)
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
