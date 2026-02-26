import typer
import yaml
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from brimley.core.context import BrimleyContext
from brimley.config.loader import load_config
from brimley.infrastructure.database import initialize_databases
from brimley.discovery.scanner import Scanner
from brimley.discovery.schema_converter import convert_json_schema_to_fieldspec
from brimley.core.registry import Registry
from brimley.execution.execute_helper import execute_function_by_name
from brimley.cli.build import compile_assets
from brimley.cli.formatter import OutputFormatter
from brimley.cli.repl import BrimleyREPL
from brimley.mcp.fastmcp_provider import BrimleyProvider
from brimley.runtime import BrimleyRuntimeController
from brimley.runtime.daemon import (
    DaemonMetadata,
    DaemonState,
    allocate_ephemeral_port,
    acquire_repl_client_slot,
    probe_daemon_state,
    recover_stale_daemon_metadata,
    release_repl_client_slot,
    shutdown_daemon_lifecycle,
    utc_now_iso,
    wait_for_daemon_running,
    write_daemon_metadata,
)
from brimley.runtime.mcp_refresh_adapter import ExternalMCPRefreshAdapter
from brimley.runtime.repl_rpc import ReplRPCDaemon, send_repl_rpc_command

BrimleyMCPAdapter = BrimleyProvider

app = typer.Typer(name="brimley", help="Brimley CLI Interface", rich_markup_mode=None)


def _coerce_bool_like(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _resolve_optional_bool_flag(enabled: object, disabled: object, flag_name: str) -> Optional[bool]:
    enabled_bool = _coerce_bool_like(enabled)
    disabled_bool = _coerce_bool_like(disabled)
    if enabled_bool and disabled_bool:
        raise typer.BadParameter(f"Cannot use --{flag_name} and --no-{flag_name} together.")
    if enabled_bool:
        return True
    if disabled_bool:
        return False
    return None


def _read_option_value(tokens: list[str], index: int, option_name: str) -> tuple[str, int]:
    if index + 1 >= len(tokens):
        raise typer.BadParameter(f"Option {option_name} requires a value.")
    return tokens[index + 1], index + 2


def _build_repl_daemon_command(
    root_dir: Path,
    mcp_enabled_override: Optional[bool],
    auto_reload_enabled_override: Optional[bool],
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "brimley.cli.main",
        "repl-daemon",
        "--root",
        str(root_dir),
    ]

    if mcp_enabled_override is True:
        command.append("--mcp")
    elif mcp_enabled_override is False:
        command.append("--no-mcp")

    if auto_reload_enabled_override is True:
        command.append("--watch")
    elif auto_reload_enabled_override is False:
        command.append("--no-watch")

    return command


def _launch_repl_daemon_process(
    root_dir: Path,
    mcp_enabled_override: Optional[bool],
    auto_reload_enabled_override: Optional[bool],
) -> subprocess.Popen:
    command = _build_repl_daemon_command(
        root_dir=root_dir,
        mcp_enabled_override=mcp_enabled_override,
        auto_reload_enabled_override=auto_reload_enabled_override,
    )
    env = os.environ.copy()
    src_dir = Path(__file__).resolve().parents[2]
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}:{existing_pythonpath}" if existing_pythonpath else str(src_dir)
    return subprocess.Popen(command, env=env)


def _run_repl_thin_client_loop(root_dir: Path, daemon_host: str, daemon_port: int) -> None:
    OutputFormatter.log(
        f"Attached thin client to daemon control API at {daemon_host}:{daemon_port}.",
        severity="success",
    )
    OutputFormatter.log("Brimley REPL thin client. Type '/help' for admin commands or '/quit' to exit.", severity="info")

    prompt_session: Optional[PromptSession] = None
    if sys.stdin.isatty():
        history_file = root_dir / ".brimley" / "repl_client_history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_session = PromptSession(history=FileHistory(str(history_file)))

    while True:
        try:
            if prompt_session is not None:
                command_line = prompt_session.prompt("brimley > ")
            else:
                command_line = typer.prompt("brimley >", prompt_suffix=" ", default="", show_default=False)
            if not command_line:
                continue

            stripped = command_line.strip()
            if stripped in {"/detach"}:
                OutputFormatter.log("Detaching thin client. Daemon remains running.", severity="info")
                break

            if stripped in {"quit", "exit", "/quit", "/exit"}:
                response = send_repl_rpc_command(daemon_host, daemon_port, "/quit")
                if response.output:
                    typer.echo(response.output, nl=False)
                if not response.ok:
                    OutputFormatter.log(response.error or "Daemon command failed.", severity="error")
                else:
                    OutputFormatter.log("Daemon session terminated.", severity="info")
                break

            response = send_repl_rpc_command(daemon_host, daemon_port, stripped)
            if response.output:
                typer.echo(response.output, nl=False)
            if not response.ok:
                OutputFormatter.log(response.error or "Daemon command failed.", severity="error")
                continue
            if not response.continue_session:
                OutputFormatter.log("Daemon session ended by remote command.", severity="warning")
                break

        except (KeyboardInterrupt, EOFError):
            OutputFormatter.log("\nDetaching thin client. Daemon remains running.", severity="info")
            break


def _derive_namespace_from_diagnostic(diagnostic) -> str:
    file_path = str(getattr(diagnostic, "file_path", "") or "")
    message = str(getattr(diagnostic, "message", "") or "")
    error_code = str(getattr(diagnostic, "error_code", "") or "")
    text = f"{file_path} {message} {error_code}".lower()
    if "mcp" in text:
        return "mcp"
    return "brimley"


def _derive_kind_from_file_path(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".md":
        return "template_function"
    if suffix == ".sql":
        return "sql_function"
    if suffix == ".py":
        return "python_function"
    return "unknown"


def _diagnostic_to_validation_issue(diagnostic) -> dict:
    file_path = str(getattr(diagnostic, "file_path", "") or "")
    line_number = getattr(diagnostic, "line_number", None)
    location = file_path
    if line_number is not None:
        location = f"{file_path}:{line_number}"

    return {
        "object_kind": _derive_kind_from_file_path(file_path),
        "namespace": _derive_namespace_from_diagnostic(diagnostic),
        "name": Path(file_path).stem if file_path else "unknown",
        "source_location": location,
        "severity": str(getattr(diagnostic, "severity", "error") or "error"),
        "code": str(getattr(diagnostic, "error_code", "UNKNOWN") or "UNKNOWN"),
        "message": str(getattr(diagnostic, "message", "") or ""),
        "remediation_hint": getattr(diagnostic, "suggestion", None),
    }


def _render_validation_text_report(payload: dict) -> str:
    summary = payload["summary"]
    lines: list[str] = [
        "Brimley Validation Report",
        (
            "Summary: "
            f"errors={summary['errors']}, warnings={summary['warnings']}, "
            f"infos={summary['infos']}, total={summary['total']}"
        ),
    ]

    issues = payload["issues"]
    if not issues:
        lines.append("No diagnostics found.")
        return "\n".join(lines)

    lines.append("Issues:")
    for issue in issues:
        lines.append(
            (
                f"- [{issue['severity'].upper()}] {issue['code']} "
                f"({issue['namespace']}/{issue['object_kind']}:{issue['name']}) "
                f"at {issue['source_location']}: {issue['message']}"
            )
        )
    return "\n".join(lines)


def _render_schema_convert_text_report(payload: dict) -> str:
    summary = payload["summary"]
    lines: list[str] = [
        "Brimley Schema Conversion Report",
        (
            "Summary: "
            f"converted_fields={summary['converted_fields']}, "
            f"errors={summary['errors']}, warnings={summary['warnings']}"
        ),
    ]

    issues = payload["issues"]
    if not issues:
        lines.append("No conversion issues.")
        return "\n".join(lines)

    lines.append("Issues:")
    for issue in issues:
        lines.append(
            f"- [{issue['severity'].upper()}] {issue['code']} at {issue['path']}: {issue['message']}"
        )
    return "\n".join(lines)

@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def repl(
    ctx: typer.Context,
):
    """
    Start an interactive REPL session.
    """
    effective_root = Path(".")
    mcp = False
    no_mcp = False
    watch = False
    no_watch = False
    shutdown_daemon = False

    tokens = list(ctx.args)
    extras: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("--root", "-r"):
            root_value, index = _read_option_value(tokens, index, token)
            effective_root = Path(root_value)
            continue
        if token.startswith("--root="):
            effective_root = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token == "--mcp":
            mcp = True
            index += 1
            continue
        if token == "--no-mcp":
            no_mcp = True
            index += 1
            continue
        if token == "--watch":
            watch = True
            index += 1
            continue
        if token == "--no-watch":
            no_watch = True
            index += 1
            continue
        if token == "--shutdown-daemon":
            shutdown_daemon = True
            index += 1
            continue
        if token.startswith("-"):
            raise typer.BadParameter(f"Unknown option: {token}")
        extras.append(token)
        index += 1

    if extras and effective_root == Path("."):
        effective_root = Path(extras.pop(0))
    if extras:
        raise typer.BadParameter(f"Unexpected arguments: {' '.join(extras)}")

    if shutdown_daemon:
        probe = probe_daemon_state(effective_root)
        if probe.state == DaemonState.RUNNING and probe.metadata is not None:
            try:
                send_repl_rpc_command(probe.metadata.host, probe.metadata.port, "/quit", timeout_seconds=1.0)
            except Exception:
                pass
        removed = shutdown_daemon_lifecycle(effective_root)
        if removed:
            OutputFormatter.log("Daemon shutdown requested: cleared daemon/client lifecycle metadata.", severity="info")
        else:
            OutputFormatter.log("Daemon shutdown requested: no daemon metadata found.", severity="info")
        raise typer.Exit(code=0)

    daemon_probe = probe_daemon_state(effective_root)
    if daemon_probe.state == DaemonState.RUNNING and daemon_probe.metadata is not None:
        OutputFormatter.log(
            (
                "Detected running daemon metadata "
                f"(pid={daemon_probe.metadata.pid}, port={daemon_probe.metadata.port})."
            ),
            severity="info",
        )
    elif daemon_probe.state == DaemonState.STALE:
        recovered = recover_stale_daemon_metadata(effective_root)
        if recovered:
            OutputFormatter.log("Recovered stale daemon metadata. Continuing REPL bootstrap.", severity="warning")
        else:
            OutputFormatter.log(f"Stale daemon metadata detected: {daemon_probe.reason}", severity="warning")
    else:
        OutputFormatter.log("No daemon metadata found. Continuing REPL bootstrap.", severity="info")

    if not acquire_repl_client_slot(effective_root):
        OutputFormatter.log(
            "Another REPL client is already attached to this daemon. Use --shutdown-daemon if recovery is required.",
            severity="error",
        )
        raise typer.Exit(code=1)

    mcp_enabled_override = _resolve_optional_bool_flag(mcp, no_mcp, "mcp")
    auto_reload_enabled_override = _resolve_optional_bool_flag(watch, no_watch, "watch")
    require_daemon_owned_mcp = mcp_enabled_override is True
    force_daemon_bootstrap = os.environ.get("BRIMLEY_FORCE_DAEMON_BOOTSTRAP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    compatibility_inprocess_mode = (
        (not sys.stdin.isatty()) or ("PYTEST_CURRENT_TEST" in os.environ)
    ) and not force_daemon_bootstrap and not require_daemon_owned_mcp
    if compatibility_inprocess_mode:
        OutputFormatter.log(
            "Non-interactive REPL session detected; using compatibility in-process mode.",
            severity="info",
        )

    if daemon_probe.state == DaemonState.RUNNING and daemon_probe.metadata is not None:
        if mcp_enabled_override is not None:
            OutputFormatter.log(
                "Daemon already running; MCP mode flags are ignored on attach. Restart daemon to change MCP mode.",
                severity="warning",
            )
        if auto_reload_enabled_override is not None:
            OutputFormatter.log(
                "Daemon already running; watch mode flags are ignored on attach. Restart daemon to change watcher mode.",
                severity="warning",
            )

    bootstrap_daemon = daemon_probe.state != DaemonState.RUNNING and not compatibility_inprocess_mode
    daemon_process: Optional[subprocess.Popen] = None

    try:
        if bootstrap_daemon:
            OutputFormatter.log("Bootstrapping daemon process for REPL session...", severity="info")
            daemon_process = _launch_repl_daemon_process(
                root_dir=effective_root,
                mcp_enabled_override=mcp_enabled_override,
                auto_reload_enabled_override=auto_reload_enabled_override,
            )
            daemon_probe_after_bootstrap = wait_for_daemon_running(
                root_dir=effective_root,
                expected_pid=daemon_process.pid,
                timeout_seconds=2.0,
            )

            if (
                daemon_probe_after_bootstrap.state != DaemonState.RUNNING
                or daemon_probe_after_bootstrap.metadata is None
            ):
                try:
                    daemon_process.terminate()
                except Exception:
                    pass
                OutputFormatter.log(
                    "Daemon bootstrap failed: daemon metadata did not reach running state.",
                    severity="error",
                )
                raise typer.Exit(code=1)

            OutputFormatter.log(
                (
                    "Daemon bootstrap complete "
                    f"(pid={daemon_probe_after_bootstrap.metadata.pid}, "
                    f"port={daemon_probe_after_bootstrap.metadata.port})."
                ),
                severity="success",
            )
            _run_repl_thin_client_loop(
                effective_root,
                daemon_probe_after_bootstrap.metadata.host,
                daemon_probe_after_bootstrap.metadata.port,
            )
        else:
            if daemon_probe.state == DaemonState.RUNNING and daemon_probe.metadata is not None:
                _run_repl_thin_client_loop(
                    effective_root,
                    daemon_probe.metadata.host,
                    daemon_probe.metadata.port,
                )
            else:
                OutputFormatter.log(
                    "Daemon attach RPC is not yet implemented; running compatibility in-process REPL session.",
                    severity="warning",
                )
                repl_session = BrimleyREPL(
                    effective_root,
                    mcp_enabled_override=mcp_enabled_override,
                    auto_reload_enabled_override=auto_reload_enabled_override,
                )
                repl_session.start()
    finally:
        release_repl_client_slot(effective_root)


@app.command("repl-daemon", hidden=True, context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def repl_daemon(
    ctx: typer.Context,
):
    """Start internal daemon process for REPL runtime ownership."""
    effective_root = Path(".")
    mcp = False
    no_mcp = False
    watch = False
    no_watch = False

    tokens = list(ctx.args)
    extras: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("--root", "-r"):
            root_value, index = _read_option_value(tokens, index, token)
            effective_root = Path(root_value)
            continue
        if token.startswith("--root="):
            effective_root = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token == "--mcp":
            mcp = True
            index += 1
            continue
        if token == "--no-mcp":
            no_mcp = True
            index += 1
            continue
        if token == "--watch":
            watch = True
            index += 1
            continue
        if token == "--no-watch":
            no_watch = True
            index += 1
            continue
        if token.startswith("-"):
            raise typer.BadParameter(f"Unknown option: {token}")
        extras.append(token)
        index += 1

    if extras and effective_root == Path("."):
        effective_root = Path(extras.pop(0))
    if extras:
        raise typer.BadParameter(f"Unexpected arguments: {' '.join(extras)}")

    mcp_enabled_override = _resolve_optional_bool_flag(mcp, no_mcp, "mcp")
    auto_reload_enabled_override = _resolve_optional_bool_flag(watch, no_watch, "watch")

    daemon_port = allocate_ephemeral_port()
    metadata = DaemonMetadata(
        pid=os.getpid(),
        port=daemon_port,
        started_at=utc_now_iso(),
    )
    write_daemon_metadata(effective_root, metadata)
    OutputFormatter.log(
        f"Daemon process started (pid={metadata.pid}, control_port={metadata.port}).",
        severity="info",
    )

    repl_session: Optional[BrimleyREPL] = None
    try:
        repl_session = BrimleyREPL(
            effective_root,
            mcp_enabled_override=mcp_enabled_override,
            auto_reload_enabled_override=auto_reload_enabled_override,
        )
        repl_session.load()
        repl_session.start_auto_reload()
        rpc_daemon = ReplRPCDaemon(host=metadata.host, port=metadata.port, repl_session=repl_session)
        rpc_daemon.serve_forever()
    finally:
        if repl_session is not None:
            try:
                repl_session.stop_auto_reload()
            except Exception:
                pass
            try:
                repl_session._shutdown_mcp_server()
            except Exception:
                pass
        shutdown_daemon_lifecycle(effective_root)


@app.command("mcp-serve", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def mcp_serve(
    ctx: typer.Context,
):
    """
    Start a non-REPL MCP server.
    """
    root_path = Path(".")
    watch = False
    no_watch = False
    host: Optional[str] = None
    port: Optional[int] = None

    tokens = list(ctx.args)
    extras: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("--root", "-r"):
            root_value, index = _read_option_value(tokens, index, token)
            root_path = Path(root_value)
            continue
        if token.startswith("--root="):
            root_path = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token == "--watch":
            watch = True
            index += 1
            continue
        if token == "--no-watch":
            no_watch = True
            index += 1
            continue
        if token == "--host":
            host, index = _read_option_value(tokens, index, token)
            continue
        if token.startswith("--host="):
            host = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--port":
            port_value, index = _read_option_value(tokens, index, token)
            try:
                port = int(port_value)
            except ValueError as exc:
                raise typer.BadParameter("Option --port must be an integer.") from exc
            continue
        if token.startswith("--port="):
            port_value = token.split("=", 1)[1]
            try:
                port = int(port_value)
            except ValueError as exc:
                raise typer.BadParameter("Option --port must be an integer.") from exc
            index += 1
            continue
        if token.startswith("-"):
            raise typer.BadParameter(f"Unknown option: {token}")
        extras.append(token)
        index += 1

    if extras:
        raise typer.BadParameter(f"Unexpected arguments: {' '.join(extras)}")
    if port is not None and not (1 <= port <= 65535):
        raise typer.BadParameter("Option --port must be between 1 and 65535.")

    watch_override = _resolve_optional_bool_flag(watch, no_watch, "watch")

    config_path = root_path / "brimley.yaml"
    if not config_path.exists():
        config_path = Path.cwd() / "brimley.yaml"

    context = BrimleyContext(config_dict=load_config(config_path))
    context.app["root_dir"] = str(root_path.expanduser().resolve())

    effective_watch = watch_override if watch_override is not None else context.auto_reload.enabled
    effective_host = host if host is not None else context.mcp.host
    effective_port = port if port is not None else context.mcp.port

    runtime_controller: Optional[BrimleyRuntimeController] = None
    mcp_server = None

    if effective_watch:
        runtime_controller = BrimleyRuntimeController(root_dir=root_path)
        server_state = {"server": None}

        def _server_factory():
            mcp_adapter = BrimleyMCPAdapter(
                registry=runtime_controller.context.functions,
                context=runtime_controller.context,
            )
            fastmcp_cls = mcp_adapter.require_fastmcp()
            return fastmcp_cls(name="BrimleyTools")

        refresh_adapter = ExternalMCPRefreshAdapter(
            context=runtime_controller.context,
            get_server=lambda: server_state["server"],
            set_server=lambda server: server_state.__setitem__("server", server),
            server_factory=_server_factory,
        )
        runtime_controller.mcp_refresh = refresh_adapter.refresh

        try:
            initial_result = runtime_controller.load_initial()
        except RuntimeError as exc:
            OutputFormatter.log(str(exc), severity="error")
            raise typer.Exit(code=1)
        except Exception as exc:
            OutputFormatter.log(f"Unable to initialize MCP runtime: {exc}", severity="error")
            raise typer.Exit(code=1)

        if initial_result.diagnostics:
            OutputFormatter.print_diagnostics(initial_result.diagnostics)

        mcp_server = server_state["server"]
        if mcp_server is None:
            OutputFormatter.log("No MCP tools discovered. Nothing to serve.", severity="warning")
            raise typer.Exit(code=0)

        runtime_controller.start_auto_reload(background=True)
        OutputFormatter.log("Auto-reload watcher started for mcp-serve.", severity="info")

    else:
        if root_path.exists():
            scanner = Scanner(root_path)
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
    try:
        mcp_server.run(transport="sse", host=effective_host, port=effective_port)
    except KeyboardInterrupt:
        OutputFormatter.log("MCP server interrupted. Shutting down.", severity="info")
    finally:
        if runtime_controller is not None:
            runtime_controller.stop_auto_reload()
            OutputFormatter.log("Auto-reload watcher stopped for mcp-serve.", severity="info")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def build(
    ctx: typer.Context,
):
    """Compile SQL/template assets into a Python shim module for runtime discovery."""
    root_dir = Path(".")
    output: Optional[Path] = None

    tokens = list(ctx.args)
    extras: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("--root", "-r"):
            root_value, index = _read_option_value(tokens, index, token)
            root_dir = Path(root_value)
            continue
        if token.startswith("--root="):
            root_dir = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token in ("--output", "-o"):
            output_value, index = _read_option_value(tokens, index, token)
            output = Path(output_value)
            continue
        if token.startswith("--output="):
            output = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token.startswith("-"):
            raise typer.BadParameter(f"Unknown option: {token}")
        extras.append(token)
        index += 1

    if extras:
        raise typer.BadParameter(f"Unexpected arguments: {' '.join(extras)}")

    try:
        result = compile_assets(root_dir=root_dir, output_file=output)
    except Exception as exc:
        OutputFormatter.log(f"Build failed: {exc}", severity="error")
        raise typer.Exit(code=1)

    OutputFormatter.log(
        (
            f"Generated assets at {result.output_file} "
            f"(sql={result.sql_functions}, templates={result.template_functions})"
        ),
        severity="success",
    )

    if result.diagnostics_count:
        OutputFormatter.log(
            f"Build completed with {result.diagnostics_count} scanner diagnostics.",
            severity="warning",
        )


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def validate(
    ctx: typer.Context,
):
    """Validate Brimley artifacts and emit a diagnostics report."""
    root_dir = Path(".")
    output_format = "text"
    fail_on = "error"
    output: Optional[Path] = None

    tokens = list(ctx.args)
    extras: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("--root", "-r"):
            root_value, index = _read_option_value(tokens, index, token)
            root_dir = Path(root_value)
            continue
        if token.startswith("--root="):
            root_dir = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token == "--format":
            output_format, index = _read_option_value(tokens, index, token)
            continue
        if token.startswith("--format="):
            output_format = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--fail-on":
            fail_on, index = _read_option_value(tokens, index, token)
            continue
        if token.startswith("--fail-on="):
            fail_on = token.split("=", 1)[1]
            index += 1
            continue
        if token in ("--output", "-o"):
            output_value, index = _read_option_value(tokens, index, token)
            output = Path(output_value)
            continue
        if token.startswith("--output="):
            output = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token.startswith("-"):
            raise typer.BadParameter(f"Unknown option: {token}")
        extras.append(token)
        index += 1

    if extras:
        raise typer.BadParameter(f"Unexpected arguments: {' '.join(extras)}")

    output_format = output_format.lower()
    if output_format not in {"text", "json"}:
        raise typer.BadParameter("Option --format must be one of: text, json")

    fail_on = fail_on.lower()
    if fail_on not in {"warning", "error"}:
        raise typer.BadParameter("Option --fail-on must be one of: warning, error")

    if root_dir.exists():
        scanner = Scanner(root_dir)
        scan_result = scanner.scan()
    else:
        OutputFormatter.log(f"Warning: Root directory '{root_dir}' does not exist.", severity="warning")
        from brimley.discovery.scanner import BrimleyScanResult

        scan_result = BrimleyScanResult()

    issues = [_diagnostic_to_validation_issue(diag) for diag in scan_result.diagnostics]
    summary = {
        "errors": sum(1 for diag in scan_result.diagnostics if diag.severity in {"error", "critical"}),
        "warnings": sum(1 for diag in scan_result.diagnostics if diag.severity == "warning"),
        "infos": sum(1 for diag in scan_result.diagnostics if diag.severity == "info"),
        "total": len(scan_result.diagnostics),
    }
    payload = {
        "root": str(root_dir),
        "fail_on": fail_on,
        "summary": summary,
        "issues": issues,
    }

    rendered = (
        json.dumps(payload, indent=2)
        if output_format == "json"
        else _render_validation_text_report(payload)
    )

    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered)
        except Exception as exc:
            OutputFormatter.log(f"Unable to write validation report: {exc}", severity="error")
            raise typer.Exit(code=1)

    typer.echo(rendered)

    if fail_on == "warning":
        has_failures = any(diag.severity in {"warning", "error", "critical"} for diag in scan_result.diagnostics)
    else:
        has_failures = any(diag.severity in {"error", "critical"} for diag in scan_result.diagnostics)

    if has_failures:
        raise typer.Exit(code=1)


@app.command("schema-convert", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def schema_convert(
    ctx: typer.Context,
):
    """Convert constrained JSON Schema to Brimley inline FieldSpec."""
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    allow_lossy = False
    output_format = "text"
    fail_on = "error"

    tokens = list(ctx.args)
    extras: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"--in", "-i"}:
            in_value, index = _read_option_value(tokens, index, token)
            input_path = Path(in_value)
            continue
        if token.startswith("--in="):
            input_path = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token in {"--out", "-o"}:
            out_value, index = _read_option_value(tokens, index, token)
            output_path = Path(out_value)
            continue
        if token.startswith("--out="):
            output_path = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token == "--allow-lossy":
            allow_lossy = True
            index += 1
            continue
        if token == "--format":
            output_format, index = _read_option_value(tokens, index, token)
            continue
        if token.startswith("--format="):
            output_format = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--fail-on":
            fail_on, index = _read_option_value(tokens, index, token)
            continue
        if token.startswith("--fail-on="):
            fail_on = token.split("=", 1)[1]
            index += 1
            continue
        if token.startswith("-"):
            raise typer.BadParameter(f"Unknown option: {token}")
        extras.append(token)
        index += 1

    if extras:
        raise typer.BadParameter(f"Unexpected arguments: {' '.join(extras)}")

    if input_path is None:
        raise typer.BadParameter("Option --in is required.")
    if output_path is None:
        raise typer.BadParameter("Option --out is required.")

    output_format = output_format.lower()
    if output_format not in {"text", "json"}:
        raise typer.BadParameter("Option --format must be one of: text, json")

    fail_on = fail_on.lower()
    if fail_on not in {"warning", "error"}:
        raise typer.BadParameter("Option --fail-on must be one of: warning, error")

    if not input_path.exists():
        OutputFormatter.log(f"Schema input not found: {input_path}", severity="error")
        raise typer.Exit(code=1)

    try:
        schema_payload = yaml.safe_load(input_path.read_text())
    except Exception as exc:
        OutputFormatter.log(f"Unable to read schema input: {exc}", severity="error")
        raise typer.Exit(code=1)

    if not isinstance(schema_payload, dict):
        OutputFormatter.log("Schema input must be a JSON/YAML object.", severity="error")
        raise typer.Exit(code=1)

    conversion = convert_json_schema_to_fieldspec(schema_payload, allow_lossy=allow_lossy)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump({"inline": conversion.inline}, sort_keys=False))

    report_payload = {
        "input": str(input_path),
        "output": str(output_path),
        "allow_lossy": allow_lossy,
        "fail_on": fail_on,
        "summary": {
            "converted_fields": conversion.report.converted_fields,
            "warnings": conversion.report.warnings,
            "errors": conversion.report.errors,
        },
        "issues": [issue.model_dump() for issue in conversion.report.issues],
    }

    rendered = (
        json.dumps(report_payload, indent=2)
        if output_format == "json"
        else _render_schema_convert_text_report(report_payload)
    )
    typer.echo(rendered)

    if fail_on == "warning":
        has_failures = conversion.report.errors > 0 or conversion.report.warnings > 0
    else:
        has_failures = conversion.report.errors > 0

    if has_failures:
        raise typer.Exit(code=1)

@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def invoke(
    ctx: typer.Context,
):
    """
    Invoke a Brimley function by name.
    """
    names = list(ctx.args)
    if not names:
        typer.echo("Error: Missing function name.", err=True)
        raise typer.Exit(code=2)

    # Workaround for argument shifting issue
    if len(names) > 1 and names[0] == "invoke":
        names.pop(0)

    function_name = names[0]

    # Compatibility fallback: some Typer/Click combinations may parse --root/--input
    # option values as extra positional args and leave option values as None.
    effective_root_dir = Path(".")
    effective_input_data = "{}"
    tail = list(names[1:])
    extras: list[str] = []
    index = 0
    while index < len(tail):
        token = tail[index]
        if token in ("--root", "-r"):
            root_value, index = _read_option_value(tail, index, token)
            effective_root_dir = Path(root_value)
            continue
        if token.startswith("--root="):
            effective_root_dir = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token in ("--input", "-i"):
            input_value, index = _read_option_value(tail, index, token)
            effective_input_data = input_value
            continue
        if token.startswith("--input="):
            effective_input_data = token.split("=", 1)[1]
            index += 1
            continue
        if token.startswith("-"):
            raise typer.BadParameter(f"Unknown option: {token}")
        extras.append(token)
        index += 1

    if extras:
        if effective_root_dir == Path("."):
            effective_root_dir = Path(extras.pop(0))
        if extras and effective_input_data == "{}":
            effective_input_data = extras.pop(0)
    if extras:
        raise typer.BadParameter(f"Unexpected arguments: {' '.join(extras)}")

    # 1. Load Context & Resources
    root_path = effective_root_dir
    config_path = root_path / "brimley.yaml"
    if not config_path.exists():
        config_path = Path.cwd() / "brimley.yaml"
        
    config_data = load_config(config_path)
    context = BrimleyContext(config_dict=config_data)
    context.app["root_dir"] = str(root_path.expanduser().resolve())

    # Hydrate databases
    if context.databases:
        context.databases = initialize_databases(context.databases, base_dir=root_path)
    
    # 2. Scan & Register
    if root_path.exists():
        scanner = Scanner(root_path)
        scan_result = scanner.scan()
    else:
        OutputFormatter.log(f"Warning: Root directory '{effective_root_dir}' does not exist.", severity="warning")
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

    # 3. Parse Input
    parsed_input = {}
    if effective_input_data and effective_input_data.strip():
        # Check if it is a file
        p = Path(effective_input_data)
        # If the string is likely a path and exists
        if len(effective_input_data) < 256 and p.exists() and p.is_file():
            content = p.read_text()
        else:
            content = effective_input_data
            
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

    # 4. Execute
    try:
        result = execute_function_by_name(
            context=context,
            function_name=function_name,
            input_data=parsed_input,
        )
    except KeyError:
        OutputFormatter.log(f"Error: Function '{function_name}' not found.", severity="error")
        available = [f.name for f in context.functions]
        OutputFormatter.log(f"Available: {available}", severity="info")
        raise typer.Exit(code=1)
    except ValueError as e:
        OutputFormatter.log(f"Error Resolving Arguments: {e}", severity="error")
        raise typer.Exit(code=1)
    except Exception as e:
        OutputFormatter.log(f"Execution Error: {e}", severity="error")
        raise typer.Exit(code=1)

    # 5. Output
    OutputFormatter.print_data(result)

if __name__ == "__main__":
    app()
