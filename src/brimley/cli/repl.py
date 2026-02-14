import typer
import yaml
import shlex
import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional
import sys
from prompt_toolkit import PromptSession

from brimley.core.context import BrimleyContext
from brimley.config.loader import load_config
from brimley.infrastructure.database import initialize_databases
from brimley.discovery.scanner import Scanner, BrimleyScanResult
from brimley.execution.dispatcher import Dispatcher
from brimley.execution.arguments import ArgumentResolver
from brimley.cli.formatter import OutputFormatter
from brimley.mcp.adapter import BrimleyMCPAdapter
from brimley.runtime.reload_contracts import (
    ReloadCommandResult,
    ReloadCommandStatus,
    ReloadSummary,
    format_reload_command_message,
)
from brimley.runtime.polling_watcher import PollingWatcher
from brimley.runtime.reload_engine import PartitionedReloadEngine

class BrimleyREPL:
    def __init__(
        self,
        root_dir: Path,
        mcp_enabled_override: Optional[bool] = None,
        auto_reload_enabled_override: Optional[bool] = None,
        reload_handler: Optional[Callable[[], ReloadCommandResult]] = None,
    ):
        self.root_dir = root_dir
        self.mcp_enabled_override = mcp_enabled_override
        self.auto_reload_enabled_override = auto_reload_enabled_override
        self.reload_handler = reload_handler
        
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

        # CLI override takes precedence over config/default
        self.auto_reload_enabled = (
            self.auto_reload_enabled_override
            if self.auto_reload_enabled_override is not None
            else self.context.auto_reload.enabled
        )
        
        # Hydrate databases
        if self.context.databases:
            self.context.databases = initialize_databases(self.context.databases)
        
        self.dispatcher = Dispatcher()
        self.prompt_session = PromptSession()
        self.mcp_server = None
        self.mcp_server_thread = None
        self.auto_reload_watcher: Optional[PollingWatcher] = None
        self.auto_reload_thread: Optional[threading.Thread] = None
        self._auto_reload_stop_event = threading.Event()
        self.reload_engine = PartitionedReloadEngine()

        if self.reload_handler is None:
            self.reload_handler = self._run_reload_cycle

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

        self._initialize_mcp_server()

    def _initialize_mcp_server(self) -> None:
        """
        Start embedded MCP server in background when enabled and tools are present.
        """
        if not self.mcp_embedded_enabled:
            return

        adapter = BrimleyMCPAdapter(registry=self.context.functions, context=self.context)
        tools = adapter.discover_tools()
        if not tools:
            return

        if not adapter.is_fastmcp_available():
            OutputFormatter.log(
                "MCP tools found, but 'fastmcp' is not installed. Skipping embedded MCP startup.",
                severity="warning",
            )
            return

        try:
            server = adapter.register_tools()
        except Exception as exc:
            OutputFormatter.log(f"Unable to initialize embedded MCP server: {exc}", severity="warning")
            return

        self.mcp_server = server

        if hasattr(server, "run"):
            host = self.context.mcp.host
            port = self.context.mcp.port

            def run_server() -> None:
                server.run(transport="sse", host=host, port=port)

            self.mcp_server_thread = threading.Thread(target=run_server, daemon=True)
            self.mcp_server_thread.start()
            OutputFormatter.log(
                f"Embedded FastMCP server running at http://{host}:{port}/sse",
                severity="success",
            )

    def _shutdown_mcp_server(self) -> None:
        """
        Attempt graceful shutdown for embedded MCP server if supported.
        """
        if self.mcp_server and hasattr(self.mcp_server, "stop"):
            try:
                self.mcp_server.stop()
            except Exception:
                pass

        if self.mcp_server_thread and self.mcp_server_thread.is_alive():
            self.mcp_server_thread.join(timeout=1)

        self.mcp_server = None
        self.mcp_server_thread = None

    def start(self):
        OutputFormatter.log("Brimley REPL. Type '/help' for admin commands or '/quit' to exit.", severity="info")
        self.load()
        self.start_auto_reload()

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
                    self.stop_auto_reload()
                    self._shutdown_mcp_server()
                    OutputFormatter.log("Exiting Brimley REPL.", severity="info")
                    break
                    
                if command_line == "reset":
                    OutputFormatter.log("Reloading...", severity="info")
                    self.stop_auto_reload()
                    self._shutdown_mcp_server()
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
                    self.auto_reload_enabled = (
                        self.auto_reload_enabled_override
                        if self.auto_reload_enabled_override is not None
                        else self.context.auto_reload.enabled
                    )
                    
                    # Hydrate databases
                    if self.context.databases:
                        self.context.databases = initialize_databases(self.context.databases)
                        
                    self.load()
                    self.start_auto_reload()
                    OutputFormatter.log("Rescan complete.", severity="success")
                    continue

                self.handle_command(command_line)

            except (KeyboardInterrupt, EOFError):
                self.stop_auto_reload()
                self._shutdown_mcp_server()
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
            "reload": self._cmd_reload,
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
        self.stop_auto_reload()
        self._shutdown_mcp_server()
        OutputFormatter.log("Exiting Brimley REPL.", severity="info")
        return False

    def start_auto_reload(self) -> None:
        """Start background polling watcher when auto-reload mode is enabled."""
        if not self.auto_reload_enabled:
            return

        if self.auto_reload_thread and self.auto_reload_thread.is_alive():
            return

        self.auto_reload_watcher = PollingWatcher(
            root_dir=self.root_dir,
            interval_ms=self.context.auto_reload.interval_ms,
            debounce_ms=self.context.auto_reload.debounce_ms,
            include_patterns=self.context.auto_reload.include_patterns,
            exclude_patterns=self.context.auto_reload.exclude_patterns,
        )
        self.auto_reload_watcher.start()
        self._auto_reload_stop_event.clear()

        self.auto_reload_thread = threading.Thread(target=self._auto_reload_loop, daemon=True)
        self.auto_reload_thread.start()
        OutputFormatter.log("Auto-reload watcher started.", severity="info")

    def stop_auto_reload(self) -> None:
        """Stop background polling watcher if active."""
        was_running = self.auto_reload_thread is not None and self.auto_reload_thread.is_alive()

        self._auto_reload_stop_event.set()
        if self.auto_reload_thread and self.auto_reload_thread.is_alive():
            self.auto_reload_thread.join(timeout=1)

        if self.auto_reload_watcher is not None:
            self.auto_reload_watcher.stop()

        self.auto_reload_thread = None
        self.auto_reload_watcher = None

        if was_running:
            OutputFormatter.log("Auto-reload watcher stopped.", severity="info")

    def _auto_reload_loop(self) -> None:
        """Background loop that polls watched files and triggers reload cycles."""
        if self.auto_reload_watcher is None:
            return

        interval_seconds = max(self.context.auto_reload.interval_ms / 1000.0, 0.05)
        while not self._auto_reload_stop_event.is_set():
            self._auto_reload_poll_once(now=time.monotonic())
            self._auto_reload_stop_event.wait(interval_seconds)

    def _auto_reload_poll_once(self, now: float) -> ReloadCommandResult | None:
        """Run one watcher poll cycle and execute reload when debounce is satisfied."""
        if self.auto_reload_watcher is None:
            return None

        poll_result = self.auto_reload_watcher.poll(now=now)
        if not poll_result.should_reload:
            return None

        result = self.reload_handler()
        self.auto_reload_watcher.complete_reload(success=result.status == ReloadCommandStatus.SUCCESS)
        message = format_reload_command_message(result)
        severity = "success" if result.status == ReloadCommandStatus.SUCCESS else "error"
        OutputFormatter.log(message, severity=severity)
        if result.diagnostics:
            OutputFormatter.print_diagnostics(result.diagnostics)

        return result

    def _cmd_help(self, args) -> bool:
        commands = [
            ("/settings", "Dumps internal framework configuration (read-only)."),
            ("/config", "Dumps user application configuration (read-only)."),
            ("/state", "Dumps current mutable application state."),
            ("/functions", "Lists all registered functions and their types."),
            ("/entities", "Lists all registered entities."),
            ("/databases", "Lists configured database connections."),
            ("/reload", "Triggers one immediate reload cycle."),
            ("/help", "Lists available admin commands."),
            ("/quit", "Exits the REPL."),
        ]
        OutputFormatter.log("\nAvailable Admin Commands:", severity="info")
        for cmd, desc in commands:
            typer.echo(f"  {cmd:<12} {desc}")
        typer.echo("")
        return True

    def _cmd_reload(self, args) -> bool:
        OutputFormatter.log("Reload requested.", severity="info")
        result = self.reload_handler()

        message = format_reload_command_message(result)
        severity = "success" if result.status == ReloadCommandStatus.SUCCESS else "error"
        OutputFormatter.log(message, severity=severity)

        if result.diagnostics:
            OutputFormatter.print_diagnostics(result.diagnostics)

        return True

    def _run_reload_cycle(self) -> ReloadCommandResult:
        """Execute one reload cycle and return standardized reload command result."""
        if self.root_dir.exists():
            scanner = Scanner(self.root_dir)
            scan_result = scanner.scan()
        else:
            scan_result = BrimleyScanResult()

        application_result = self.reload_engine.apply_reload_with_policy(self.context, scan_result)
        status = (
            ReloadCommandStatus.FAILURE
            if application_result.blocked_domains
            else ReloadCommandStatus.SUCCESS
        )

        if status == ReloadCommandStatus.SUCCESS:
            self._refresh_embedded_mcp_server_after_reload()

        return ReloadCommandResult(
            status=status,
            summary=application_result.summary,
            diagnostics=application_result.diagnostics,
        )

    def _refresh_embedded_mcp_server_after_reload(self) -> None:
        """Refresh embedded MCP tools after successful reload with in-place preference."""
        if not self.mcp_embedded_enabled:
            return

        adapter = BrimleyMCPAdapter(registry=self.context.functions, context=self.context)
        tools = adapter.discover_tools()

        if not tools:
            if self.mcp_server is not None or self.mcp_server_thread is not None:
                self._shutdown_mcp_server()
            return

        if not adapter.is_fastmcp_available():
            OutputFormatter.log(
                "MCP tools found, but 'fastmcp' is not installed. Skipping embedded MCP refresh.",
                severity="warning",
            )
            return

        if self.mcp_server is None and self.mcp_server_thread is None:
            self._initialize_mcp_server()
            return

        if self.mcp_server is not None and self._supports_tool_reset(self.mcp_server):
            try:
                self._clear_server_tools(self.mcp_server)
                adapter.register_tools(mcp_server=self.mcp_server)
                OutputFormatter.log("Embedded MCP tools refreshed.", severity="success")
            except Exception as exc:
                OutputFormatter.log(f"Unable to refresh embedded MCP tools in place: {exc}", severity="warning")
            return

        if self.mcp_server is not None and hasattr(self.mcp_server, "stop"):
            self._shutdown_mcp_server()
            self._initialize_mcp_server()
            return

        OutputFormatter.log(
            "Embedded MCP server does not support in-place tool reset; keeping existing MCP server running.",
            severity="warning",
        )

    def _supports_tool_reset(self, server: object) -> bool:
        return callable(getattr(server, "clear_tools", None)) or callable(getattr(server, "reset_tools", None))

    def _clear_server_tools(self, server: object) -> None:
        clear_tools = getattr(server, "clear_tools", None)
        if callable(clear_tools):
            clear_tools()
            return

        reset_tools = getattr(server, "reset_tools", None)
        if callable(reset_tools):
            reset_tools()

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
