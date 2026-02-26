import pytest
import json
import typer
from types import SimpleNamespace
from typer.testing import CliRunner
from brimley.cli.main import app, _resolve_optional_bool_flag
from brimley.runtime.daemon import DaemonMetadata, DaemonProbeResult, DaemonState
from brimley.utils.diagnostics import BrimleyDiagnostic
from pathlib import Path

runner = CliRunner()


def _combined_output(result) -> str:
    return f"{result.stdout}{getattr(result, 'stderr', '')}"

def test_invoke_help():
    result = runner.invoke(app, ["invoke", "--help"])
    assert result.exit_code == 0
    assert "Invoke a Brimley function" in result.stdout

def test_invoke_missing_function():
    result = runner.invoke(app, ["invoke", "non_existent_func"])
    assert result.exit_code == 1
    assert "Function 'non_existent_func' not found" in _combined_output(result)

def test_invoke_template_function(tmp_path):
    # Setup: Create a meaningful directory structure
    (tmp_path / "funcs").mkdir()
    
    # Create the function file
    func_file = tmp_path / "funcs" / "hello.md"
    func_file.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string
---
Hello {{ args.name }}""")

    # Run CLI pointing to this root
    # Warning: We rely on Scanner finding it.
    
    result = runner.invoke(app, ["invoke", "hello", "--root", str(tmp_path / "funcs"), "--input", '{"name": "CLI"}'])
    
    if result.exit_code != 0:
        print(f"FAILED OUTPUT:\n{result.stdout}")

    assert result.exit_code == 0
    assert "Hello CLI" in result.stdout


def test_invoke_template_function_with_dot_root_from_cwd(monkeypatch, tmp_path):
        func_file = tmp_path / "hello.md"
        func_file.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
    inline:
        name: string
---
Hello {{ args.name }}""")

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["invoke", "hello", "--root", ".", "--input", '{"name": "CLI"}'])

        assert result.exit_code == 0
        assert "Hello CLI" in result.stdout

def test_invoke_with_invalid_yaml(tmp_path):
    # Need a valid function first
    (tmp_path / "f.md").write_text("""---
name: f
type: template_function
return_shape: void
---
""")
    result = runner.invoke(app, ["invoke", "f", "--root", str(tmp_path), "--input", "{invalid"])
    assert result.exit_code == 1
    assert "Invalid YAML" in _combined_output(result)

def test_invoke_sql_function_json_output(tmp_path):
    # 1. Create brimley.yaml with a database
    config = tmp_path / "brimley.yaml"
    config.write_text("""
databases:
  default:
    url: "sqlite:///:memory:"
""")
    
    # 2. Setup: Create users table in that in-memory DB? 
    # Hard to do via CLI directly if it's transient.
    # Let's use a file-based SQLite instead so we can prep it.
    db_path = tmp_path / "test.db"
    config.write_text(f"""
databases:
  default:
    url: "sqlite:///{db_path}"
""")
    
    # Prep the DB
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id int, name text)"))
        conn.execute(text("INSERT INTO users VALUES (123, 'CLI User')"))
        conn.commit()

    # 3. Create the SQL function
    (tmp_path / "sql").mkdir()
    f = tmp_path / "sql" / "get_users.sql"
    f.write_text("""/*
---
type: sql_function
name: get_users
return_shape: list[dict]
arguments:
  inline:
    id: int
---
*/
SELECT * FROM users WHERE id = :id
""")
    
    result = runner.invoke(app, ["invoke", "get_users", 
                                 "--root", str(tmp_path), 
                                 "--input", '{"id": 123}'])
    
    if result.exit_code != 0:
        print(f"FAILED OUTPUT:\n{result.stdout}")

    assert result.exit_code == 0
    # The output should now be a JSON list of dicts
    assert "CLI User" in result.stdout
    assert "123" in result.stdout


def test_invoke_sql_function_resolves_relative_sqlite_url_from_root(monkeypatch, tmp_path):
    root = tmp_path / "examples"
    root.mkdir()

    (root / "brimley.yaml").write_text(
        """
databases:
  default:
    url: "sqlite:///./data.db"
"""
    )

    db_path = root / "data.db"
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id int, username text, email text)"))
        conn.execute(text("INSERT INTO users VALUES (1, 'relative-user', 'relative@example.com')"))
        conn.commit()

    (root / "get_users.sql").write_text(
        """/*
---
type: sql_function
name: get_users
connection: default
return_shape: list[dict]
arguments:
  inline:
    limit: int
---
*/
SELECT id, username, email
FROM users
ORDER BY id DESC
LIMIT :limit
"""
    )

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["invoke", "get_users", "--root", str(root), "--input", '{"limit": 1}'],
    )

    assert result.exit_code == 0
    assert "relative-user" in result.stdout


def test_invoke_uses_execute_function_helper(monkeypatch, tmp_path):
    (tmp_path / "funcs").mkdir()
    func_file = tmp_path / "funcs" / "hello.md"
    func_file.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string
---
Hello {{ args.name }}""")

    captured = {}

    def fake_execute_helper(context, function_name, input_data, runtime_injections=None):
        captured["context"] = context
        captured["function_name"] = function_name
        captured["input_data"] = input_data
        captured["runtime_injections"] = runtime_injections
        return "helper-result"

    monkeypatch.setattr("brimley.cli.main.execute_function_by_name", fake_execute_helper)

    result = runner.invoke(
        app,
        ["invoke", "hello", "--root", str(tmp_path / "funcs"), "--input", '{"name": "CLI"}'],
    )

    assert result.exit_code == 0
    assert "helper-result" in result.stdout
    assert captured["function_name"] == "hello"
    assert captured["input_data"] == {"name": "CLI"}
    assert captured["runtime_injections"] is None


def test_repl_flag_mcp_enables_embedded(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir
            captured["override"] = mcp_enabled_override

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path), "--mcp"])

    assert result.exit_code == 0
    assert captured["override"] is True
    assert captured["started"] is True


def test_repl_flag_no_mcp_disables_embedded(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir
            captured["override"] = mcp_enabled_override

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path), "--no-mcp"])

    assert result.exit_code == 0
    assert captured["override"] is False
    assert captured["started"] is True


def test_repl_flag_default_uses_config_or_default(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir
            captured["override"] = mcp_enabled_override

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["override"] is None
    assert captured["started"] is True


def test_repl_logs_running_daemon_metadata(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)
    monkeypatch.setattr(
        "brimley.cli.main.probe_daemon_state",
        lambda root_dir: DaemonProbeResult(
            state=DaemonState.RUNNING,
            metadata=DaemonMetadata(pid=1234, port=9010, started_at="2026-02-25T00:00:00Z"),
            metadata_path=str(root_dir / ".brimley" / "daemon.json"),
            reason="Daemon process is alive.",
        ),
    )

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)])
    output = _combined_output(result)

    assert result.exit_code == 0
    assert captured["started"] is True
    assert "Detected running daemon metadata" in output


def test_repl_recovers_stale_daemon_metadata(monkeypatch, tmp_path):
    captured = {}
    recover_calls = {"count": 0}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)
    monkeypatch.setattr(
        "brimley.cli.main.probe_daemon_state",
        lambda root_dir: DaemonProbeResult(
            state=DaemonState.STALE,
            metadata=None,
            metadata_path=str(root_dir / ".brimley" / "daemon.json"),
            reason="Daemon process pid=1234 is not alive.",
        ),
    )

    def fake_recover(root_dir):
        recover_calls["count"] += 1
        return True

    monkeypatch.setattr("brimley.cli.main.recover_stale_daemon_metadata", fake_recover)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)])
    output = _combined_output(result)

    assert result.exit_code == 0
    assert captured["started"] is True
    assert recover_calls["count"] == 1
    assert "Recovered stale daemon metadata" in output


def test_repl_rejects_when_client_slot_already_active(monkeypatch, tmp_path):
    captured = {"started": False}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)
    monkeypatch.setattr("brimley.cli.main.acquire_repl_client_slot", lambda root_dir: False)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)])
    output = _combined_output(result)

    assert result.exit_code == 1
    assert captured["started"] is False
    assert "already attached" in output.lower()


def test_repl_releases_client_slot_after_session(monkeypatch, tmp_path):
    calls = {"release": 0}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            self.root_dir = root_dir

        def start(self):
            return None

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)
    monkeypatch.setattr("brimley.cli.main.acquire_repl_client_slot", lambda root_dir: True)

    def fake_release(root_dir):
        calls["release"] += 1

    monkeypatch.setattr("brimley.cli.main.release_repl_client_slot", fake_release)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert calls["release"] == 1


def test_repl_shutdown_daemon_flag_runs_shutdown_and_exits(monkeypatch, tmp_path):
    captured = {"started": False, "shutdown": 0}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            self.root_dir = root_dir

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    def fake_shutdown(root_dir):
        captured["shutdown"] += 1
        return True

    monkeypatch.setattr("brimley.cli.main.shutdown_daemon_lifecycle", fake_shutdown)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path), "--shutdown-daemon"])
    output = _combined_output(result)

    assert result.exit_code == 0
    assert captured["shutdown"] == 1
    assert captured["started"] is False
    assert "shutdown requested" in output.lower()


def test_repl_with_dot_root_from_cwd(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["repl", "--root", "."])

    assert result.exit_code == 0
    assert captured["started"] is True
    assert str(captured["root_dir"]) == "."


def test_repl_flag_watch_enables_auto_reload(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir
            captured["mcp_override"] = mcp_enabled_override
            captured["auto_reload_override"] = auto_reload_enabled_override

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path), "--watch"])

    assert result.exit_code == 0
    assert captured["auto_reload_override"] is True
    assert captured["started"] is True


def test_repl_flag_no_watch_disables_auto_reload(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir
            captured["mcp_override"] = mcp_enabled_override
            captured["auto_reload_override"] = auto_reload_enabled_override

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path), "--no-watch"])

    assert result.exit_code == 0
    assert captured["auto_reload_override"] is False
    assert captured["started"] is True


def test_repl_flag_watch_default_uses_config_or_default(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None, auto_reload_enabled_override=None):
            captured["root_dir"] = root_dir
            captured["mcp_override"] = mcp_enabled_override
            captured["auto_reload_override"] = auto_reload_enabled_override

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["auto_reload_override"] is None
    assert captured["started"] is True


def test_resolve_optional_bool_flag_rejects_conflicting_mcp_flags():
    with pytest.raises(typer.BadParameter, match="Cannot use --mcp and --no-mcp together"):
        _resolve_optional_bool_flag(True, True, "mcp")


def test_resolve_optional_bool_flag_rejects_conflicting_watch_flags():
    with pytest.raises(typer.BadParameter, match="Cannot use --watch and --no-watch together"):
        _resolve_optional_bool_flag(True, True, "watch")


def test_mcp_serve_help():
    result = runner.invoke(app, ["mcp-serve", "--help"])

    assert result.exit_code == 0
    assert "Start a non-REPL MCP server" in result.stdout


def test_mcp_serve_rejects_conflicting_watch_flags(tmp_path):
    result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path), "--watch", "--no-watch"])

    assert result.exit_code != 0
    assert "Cannot use --watch and --no-watch together" in _combined_output(result)


def test_mcp_serve_starts_server_with_config_defaults(tmp_path, monkeypatch):
    (tmp_path / "brimley.yaml").write_text(
        """
auto_reload:
    enabled: false
mcp:
  host: 0.0.0.0
  port: 9100
"""
    )

    class FakeServer:
        def __init__(self):
            self.run_args = None

        def run(self, transport, host, port):
            self.run_args = {"transport": transport, "host": host, "port": port}

    fake_server = FakeServer()

    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return [object()]

        def register_tools(self):
            return fake_server

    logs = []
    monkeypatch.setattr("brimley.cli.main.BrimleyMCPAdapter", FakeAdapter)
    monkeypatch.setattr("brimley.cli.main.OutputFormatter.log", lambda message, severity="info": logs.append((severity, message)))

    result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert fake_server.run_args == {"transport": "sse", "host": "0.0.0.0", "port": 9100}


def test_mcp_serve_cli_overrides_host_port_and_watch(tmp_path, monkeypatch):
    (tmp_path / "brimley.yaml").write_text(
        """
auto_reload:
  enabled: true
mcp:
  host: 127.0.0.1
  port: 8000
"""
    )

    class FakeServer:
        def __init__(self):
            self.run_args = None

        def run(self, transport, host, port):
            self.run_args = {"transport": transport, "host": host, "port": port}

    fake_server = FakeServer()

    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return [object()]

        def register_tools(self):
            return fake_server

    logs = []
    monkeypatch.setattr("brimley.cli.main.BrimleyMCPAdapter", FakeAdapter)
    monkeypatch.setattr("brimley.cli.main.OutputFormatter.log", lambda message, severity="info": logs.append((severity, message)))

    result = runner.invoke(
        app,
        ["mcp-serve", "--root", str(tmp_path), "--no-watch", "--host", "0.0.0.0", "--port", "9200"],
    )

    assert result.exit_code == 0
    assert fake_server.run_args == {"transport": "sse", "host": "0.0.0.0", "port": 9200}
    assert not any("Watch mode for mcp-serve is planned for AR-P8-S3" in message for _, message in logs)


def test_mcp_serve_exits_success_when_no_tools(tmp_path, monkeypatch):
    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return []

    monkeypatch.setattr("brimley.cli.main.BrimleyMCPAdapter", FakeAdapter)

    result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "No MCP tools discovered" in _combined_output(result)


def test_mcp_serve_errors_when_fastmcp_missing(tmp_path, monkeypatch):
    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return [object()]

        def register_tools(self):
            raise RuntimeError("MCP tools found but 'fastmcp' is not installed.")

    monkeypatch.setattr("brimley.cli.main.BrimleyMCPAdapter", FakeAdapter)

    result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "fastmcp" in _combined_output(result).lower()


def test_mcp_serve_watch_mode_starts_and_stops_runtime_controller(tmp_path, monkeypatch):
    class FakeServer:
        def __init__(self):
            self.run_args = None

        def run(self, transport, host, port):
            self.run_args = {"transport": transport, "host": host, "port": port}

    class FakeRuntimeController:
        started = 0
        stopped = 0

        def __init__(self, root_dir):
            self.root_dir = root_dir
            self.context = SimpleNamespace()
            self.mcp_refresh = None

        def load_initial(self):
            if self.mcp_refresh is not None:
                self.mcp_refresh()
            return SimpleNamespace(diagnostics=[])

        def start_auto_reload(self, background=True):
            assert background is True
            FakeRuntimeController.started += 1

        def stop_auto_reload(self):
            FakeRuntimeController.stopped += 1

    class FakeRefreshAdapter:
        def __init__(self, context, get_server, set_server, server_factory=None):
            self.get_server = get_server
            self.set_server = set_server

        def refresh(self):
            server = FakeServer()
            self.set_server(server)
            return server

    monkeypatch.setattr("brimley.cli.main.BrimleyRuntimeController", FakeRuntimeController)
    monkeypatch.setattr("brimley.cli.main.ExternalMCPRefreshAdapter", FakeRefreshAdapter)

    result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path), "--watch"])

    assert result.exit_code == 0
    assert FakeRuntimeController.started == 1
    assert FakeRuntimeController.stopped == 1


def test_mcp_serve_watch_mode_handles_keyboard_interrupt_and_stops_runtime(tmp_path, monkeypatch):
    class InterruptServer:
        def run(self, transport, host, port):
            raise KeyboardInterrupt

    class FakeRuntimeController:
        stopped = 0

        def __init__(self, root_dir):
            self.root_dir = root_dir
            self.context = SimpleNamespace()
            self.mcp_refresh = None

        def load_initial(self):
            if self.mcp_refresh is not None:
                self.mcp_refresh()
            return SimpleNamespace(diagnostics=[])

        def start_auto_reload(self, background=True):
            return None

        def stop_auto_reload(self):
            FakeRuntimeController.stopped += 1

    class FakeRefreshAdapter:
        def __init__(self, context, get_server, set_server, server_factory=None):
            self.set_server = set_server

        def refresh(self):
            server = InterruptServer()
            self.set_server(server)
            return server

    monkeypatch.setattr("brimley.cli.main.BrimleyRuntimeController", FakeRuntimeController)
    monkeypatch.setattr("brimley.cli.main.ExternalMCPRefreshAdapter", FakeRefreshAdapter)

    result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path), "--watch"])

    assert result.exit_code == 0
    assert FakeRuntimeController.stopped == 1


def test_mcp_serve_watch_mode_exits_when_no_tools_before_starting_watcher(tmp_path, monkeypatch):
    class FakeRuntimeController:
        started = 0

        def __init__(self, root_dir):
            self.root_dir = root_dir
            self.context = SimpleNamespace()
            self.mcp_refresh = None

        def load_initial(self):
            return SimpleNamespace(diagnostics=[])

        def start_auto_reload(self, background=True):
            FakeRuntimeController.started += 1

        def stop_auto_reload(self):
            return None

    class FakeRefreshAdapter:
        def __init__(self, context, get_server, set_server, server_factory=None):
            pass

        def refresh(self):
            return None

    monkeypatch.setattr("brimley.cli.main.BrimleyRuntimeController", FakeRuntimeController)
    monkeypatch.setattr("brimley.cli.main.ExternalMCPRefreshAdapter", FakeRefreshAdapter)

    result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path), "--watch"])

    assert result.exit_code == 0
    assert "No MCP tools discovered" in _combined_output(result)
    assert FakeRuntimeController.started == 0


def test_validate_help():
    result = runner.invoke(app, ["validate", "--help"])

    assert result.exit_code == 0
    assert "Validate Brimley artifacts" in result.stdout


def test_validate_default_threshold_fails_on_error(monkeypatch, tmp_path):
    class FakeScanner:
        def __init__(self, root_dir):
            self.root_dir = root_dir

        def scan(self):
            return SimpleNamespace(
                diagnostics=[
                    BrimleyDiagnostic(
                        file_path="broken.md",
                        error_code="ERR_PARSE_FAILURE",
                        message="bad frontmatter",
                        severity="error",
                    )
                ]
            )

    monkeypatch.setattr("brimley.cli.main.Scanner", FakeScanner)

    result = runner.invoke(app, ["validate", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "Brimley Validation Report" in result.stdout
    assert "ERR_PARSE_FAILURE" in result.stdout


def test_validate_default_threshold_ignores_warning(monkeypatch, tmp_path):
    class FakeScanner:
        def __init__(self, root_dir):
            self.root_dir = root_dir

        def scan(self):
            return SimpleNamespace(
                diagnostics=[
                    BrimleyDiagnostic(
                        file_path="warn.md",
                        error_code="WARN_NAME_PROXIMITY",
                        message="name is too close",
                        severity="warning",
                    )
                ]
            )

    monkeypatch.setattr("brimley.cli.main.Scanner", FakeScanner)

    result = runner.invoke(app, ["validate", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "WARN_NAME_PROXIMITY" in result.stdout


def test_validate_fail_on_warning_exits_non_zero(monkeypatch, tmp_path):
    class FakeScanner:
        def __init__(self, root_dir):
            self.root_dir = root_dir

        def scan(self):
            return SimpleNamespace(
                diagnostics=[
                    BrimleyDiagnostic(
                        file_path="warn.md",
                        error_code="WARN_NAME_PROXIMITY",
                        message="name is too close",
                        severity="warning",
                    )
                ]
            )

    monkeypatch.setattr("brimley.cli.main.Scanner", FakeScanner)

    result = runner.invoke(app, ["validate", "--root", str(tmp_path), "--fail-on", "warning"])

    assert result.exit_code == 1
    assert "WARN_NAME_PROXIMITY" in result.stdout


def test_validate_json_format_and_output_file(monkeypatch, tmp_path):
    class FakeScanner:
        def __init__(self, root_dir):
            self.root_dir = root_dir

        def scan(self):
            return SimpleNamespace(
                diagnostics=[
                    BrimleyDiagnostic(
                        file_path="broken.sql",
                        error_code="ERR_PARSE_FAILURE",
                        message="bad sql metadata",
                        severity="error",
                        line_number=12,
                        suggestion="Fix frontmatter",
                    )
                ]
            )

    monkeypatch.setattr("brimley.cli.main.Scanner", FakeScanner)
    report_file = tmp_path / "reports" / "validate.json"

    result = runner.invoke(
        app,
        [
            "validate",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--output",
            str(report_file),
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["summary"]["errors"] == 1
    assert payload["issues"][0]["object_kind"] == "sql_function"
    assert payload["issues"][0]["source_location"] == "broken.sql:12"
    assert payload["issues"][0]["remediation_hint"] == "Fix frontmatter"
    assert report_file.exists()
    file_payload = json.loads(report_file.read_text())
    assert file_payload["issues"][0]["code"] == "ERR_PARSE_FAILURE"


def test_schema_convert_help():
    result = runner.invoke(app, ["schema-convert", "--help"])

    assert result.exit_code == 0
    assert "Convert constrained JSON Schema" in result.stdout


def test_schema_convert_strict_fails_on_unsupported_keyword(tmp_path):
    input_file = tmp_path / "schema.json"
    output_file = tmp_path / "fieldspec.yaml"
    input_file.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "x-extra": "unsupported",
                    }
                },
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "schema-convert",
            "--in",
            str(input_file),
            "--out",
            str(output_file),
        ],
    )

    assert result.exit_code == 1
    assert "ERR_SCHEMA_UNSUPPORTED_KEYWORD" in _combined_output(result)


def test_schema_convert_allow_lossy_writes_output_and_json_report(tmp_path):
    input_file = tmp_path / "schema.json"
    output_file = tmp_path / "fieldspec.yaml"
    input_file.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "name": {"type": "string", "x-extra": "drop-me"},
                },
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "schema-convert",
            "--in",
            str(input_file),
            "--out",
            str(output_file),
            "--allow-lossy",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["warnings"] >= 1
    assert output_file.exists()
    converted = output_file.read_text()
    assert "inline:" in converted
    assert "amount" in converted


def test_schema_convert_fail_on_warning_returns_non_zero(tmp_path):
    input_file = tmp_path / "schema.json"
    output_file = tmp_path / "fieldspec.yaml"
    input_file.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                },
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "schema-convert",
            "--in",
            str(input_file),
            "--out",
            str(output_file),
            "--allow-lossy",
            "--fail-on",
            "warning",
        ],
    )

    assert result.exit_code == 1
    assert "WARN_SCHEMA_NUMBER_TO_FLOAT" in _combined_output(result)
