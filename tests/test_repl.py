import pytest
from typer.testing import CliRunner
from brimley.cli.main import app
from brimley.cli.repl import BrimleyREPL
from brimley.core.models import TemplateFunction
from pathlib import Path

runner = CliRunner()

def test_repl_quit(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="quit\n")
    assert result.exit_code == 0
    assert "Exiting Brimley REPL" in result.stdout

def test_repl_invoke_hello(tmp_path):
    # Setup
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string 
---
Hello {{ args.name }}""")

    # REPL Input: call hello, then quit
    repl_input = "hello {name: REPL}\nquit\n"
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input=repl_input)
    
    assert result.exit_code == 0
    assert "Hello REPL" in result.stdout

def test_repl_reset(tmp_path):
    (tmp_path / "funcs").mkdir()
    
    # 1. Start empty
    # 2. Add file
    # 3. 'reset'
    # 4. Call file
    
    # This is tricky because the process logic happens in memory. 
    # Scanner only scans disk. 
    # We can simulate this by mocking the scanner or writing to disk mid-test?
    # Writing to disk mid-test works if the REPL loop yields execution.
    # Typer runner input is all pre-buffered. 
    
    # We can't really modify disk "during" the `runner.invoke` call effortlessly unless we used threads.
    # We will test 'reset' simply by checking the message for now.
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path)], input="reset\nquit\n")
    assert "Reloading..." in result.stdout
    assert "Rescan complete" in result.stdout

def test_repl_file_input(tmp_path):
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string 
---
Hello {{ args.name }}""")
    
    arg_file = tmp_path / "args.json"
    arg_file.write_text('{"name": "FileLoader"}')

    # Input: hello @args.json
    repl_input = f"hello @{str(arg_file)}\nquit\n"
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input=repl_input)
    assert "Hello FileLoader" in result.stdout

def test_repl_multiline_input(tmp_path):
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string 
---
Hello {{ args.name }}""")

    # Trigger multiline by NOT providing args on first line
    # Then provide args, then empty line
    repl_input = "hello\nname: MultiLine\n\nquit\n"
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input=repl_input)
    assert "** Enter multi-line input" in result.stdout # We expect this prompt
    assert "Hello MultiLine" in result.stdout

def test_repl_admin_help(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/help\n/quit\n")
    assert "/settings" in result.stdout
    assert "/config" in result.stdout
    assert "/state" in result.stdout
    assert "/functions" in result.stdout

def test_repl_admin_settings(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/settings\n/quit\n")
    assert '"env": "development"' in result.stdout

def test_repl_admin_functions(tmp_path):
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("---\nname: hello\ntype: template_function\nreturn_shape: string\n---\nHi")
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/functions\n/quit\n")
    assert "[template_function] hello" in result.stdout

def test_repl_admin_invalid(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/unknown_cmd\n/quit\n")
    assert "Unknown admin command: /unknown_cmd" in result.stdout


def test_repl_mcp_warns_when_tools_exist_but_fastmcp_missing(tmp_path, monkeypatch):
    repl = BrimleyREPL(tmp_path, mcp_enabled_override=True)
    repl.context.functions.register(
        TemplateFunction(
            name="hello_tool",
            type="template_function",
            return_shape="string",
            template_body="Hello",
            mcp={"type": "tool"},
        )
    )

    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return [object()]

        def is_fastmcp_available(self):
            return False

    logs = []
    monkeypatch.setattr("brimley.cli.repl.BrimleyMCPAdapter", FakeAdapter)
    monkeypatch.setattr("brimley.cli.repl.OutputFormatter.log", lambda message, severity="info": logs.append((severity, message)))

    repl._initialize_mcp_server()

    assert any("fastmcp" in message.lower() and severity == "warning" for severity, message in logs)


def test_repl_mcp_starts_background_server_when_available(tmp_path, monkeypatch):
    repl = BrimleyREPL(tmp_path, mcp_enabled_override=True)
    repl.context.mcp.host = "127.0.0.1"
    repl.context.mcp.port = 8123

    class FakeServer:
        def __init__(self):
            self.run_called = False

        def run(self, transport, host, port):
            self.run_called = True
            self.transport = transport
            self.host = host
            self.port = port

    fake_server = FakeServer()

    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return [object()]

        def is_fastmcp_available(self):
            return True

        def register_tools(self):
            return fake_server

    logs = []
    monkeypatch.setattr("brimley.cli.repl.BrimleyMCPAdapter", FakeAdapter)
    monkeypatch.setattr("brimley.cli.repl.OutputFormatter.log", lambda message, severity="info": logs.append((severity, message)))

    repl._initialize_mcp_server()

    assert repl.mcp_server is fake_server
    assert repl.mcp_server_thread is not None
    repl.mcp_server_thread.join(timeout=1)
    assert fake_server.run_called is True
    assert fake_server.transport == "sse"
    assert fake_server.host == "127.0.0.1"
    assert fake_server.port == 8123
    assert any("/sse" in message for _, message in logs)


def test_repl_mcp_noop_when_no_tools(tmp_path, monkeypatch):
    repl = BrimleyREPL(tmp_path, mcp_enabled_override=True)

    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return []

        def is_fastmcp_available(self):
            raise AssertionError("Should not check fastmcp when there are no tools")

    monkeypatch.setattr("brimley.cli.repl.BrimleyMCPAdapter", FakeAdapter)

    repl._initialize_mcp_server()

    assert repl.mcp_server is None
    assert repl.mcp_server_thread is None


def test_repl_load_does_not_initialize_mcp_when_disabled(tmp_path, monkeypatch):
    (tmp_path / "tool.md").write_text("""---
name: hello_tool
type: template_function
return_shape: string
mcp:
  type: tool
---
Hello
""")

    class FailingAdapter:
        def __init__(self, registry, context):
            raise AssertionError("Adapter should not be constructed when MCP is disabled")

    monkeypatch.setattr("brimley.cli.repl.BrimleyMCPAdapter", FailingAdapter)

    repl = BrimleyREPL(tmp_path, mcp_enabled_override=False)
    repl.load()

    assert repl.mcp_server is None
    assert repl.mcp_server_thread is None


def test_repl_startup_warns_when_fastmcp_unavailable_with_tools(tmp_path, monkeypatch):
    (tmp_path / "tool.md").write_text("""---
name: hello_tool
type: template_function
return_shape: string
mcp:
  type: tool
---
Hello
""")

    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return [object()]

        def is_fastmcp_available(self):
            return False

    monkeypatch.setattr("brimley.cli.repl.BrimleyMCPAdapter", FakeAdapter)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path), "--mcp"], input="/quit\n")

    assert result.exit_code == 0
    assert "fastmcp" in result.stdout.lower()
    assert "skipping embedded mcp" in result.stdout.lower()


def test_repl_slash_quit_triggers_mcp_shutdown(tmp_path, monkeypatch):
    shutdown_calls = {"count": 0}

    def fake_shutdown(self):
        shutdown_calls["count"] += 1

    monkeypatch.setattr("brimley.cli.repl.BrimleyREPL._shutdown_mcp_server", fake_shutdown)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)], input="/quit\n")

    assert result.exit_code == 0
    assert shutdown_calls["count"] == 1


def test_repl_auto_reload_enabled_uses_config_when_no_override(tmp_path):
        (tmp_path / "brimley.yaml").write_text(
                """
auto_reload:
    enabled: true
"""
        )

        repl = BrimleyREPL(tmp_path)

        assert repl.auto_reload_enabled is True


def test_repl_auto_reload_enabled_cli_override_true(tmp_path):
        (tmp_path / "brimley.yaml").write_text(
                """
auto_reload:
    enabled: false
"""
        )

        repl = BrimleyREPL(tmp_path, auto_reload_enabled_override=True)

        assert repl.auto_reload_enabled is True


def test_repl_auto_reload_enabled_cli_override_false(tmp_path):
        (tmp_path / "brimley.yaml").write_text(
                """
auto_reload:
    enabled: true
"""
        )

        repl = BrimleyREPL(tmp_path, auto_reload_enabled_override=False)

        assert repl.auto_reload_enabled is False


def test_repl_reset_preserves_auto_reload_override_precedence(tmp_path, monkeypatch):
        (tmp_path / "brimley.yaml").write_text(
                """
auto_reload:
    enabled: true
"""
        )

        repl = BrimleyREPL(tmp_path, auto_reload_enabled_override=False)

        monkeypatch.setattr("brimley.cli.repl.sys.stdin.isatty", lambda: True)
        inputs = iter(["reset", "/quit"])
        monkeypatch.setattr(repl.prompt_session, "prompt", lambda *_args, **_kwargs: next(inputs))
        monkeypatch.setattr(repl, "load", lambda: None)
        monkeypatch.setattr(repl, "_shutdown_mcp_server", lambda: None)

        repl.start()

        assert repl.auto_reload_enabled is False
