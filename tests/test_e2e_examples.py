import pytest
import json
import os
import sys
import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from typer.testing import CliRunner
from brimley.cli.main import app
from brimley.core.context import BrimleyContext
from brimley.discovery.scanner import Scanner
from brimley.execution.execute_helper import execute_function_by_name
from brimley.mcp.mock import MockMCPContext

runner = CliRunner()
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Ensure we can import from examples logic
sys.path.append(str(EXAMPLES_DIR.parent))

def test_e2e_hello_template():
    result = runner.invoke(app, ["invoke", "hello", "--root", str(EXAMPLES_DIR), "--input", '{"name": "E2E"}'])
    assert result.exit_code == 0
    assert "Hello E2E!" in result.stdout

def test_e2e_users_sql(tmp_path):
    # Setup a local brimley.yaml and DB to avoid mess in examples
    db_path = tmp_path / "test.db"
    
    # Create the DB
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id int, username text, email text)"))
        conn.execute(text("INSERT INTO users VALUES (1, 'alice', 'alice@test.com')"))
        conn.commit()

    # Create brimley.yaml
    config = tmp_path / "brimley.yaml"
    config.write_text(f"""
databases:
  default:
    url: "sqlite:///{db_path}"
""")

    # Copy users.sql to tmp_path
    import shutil
    shutil.copy(EXAMPLES_DIR / "users.sql", tmp_path / "users.sql")

    result = runner.invoke(app, ["invoke", "get_users", "--root", str(tmp_path), "--input", '{"limit": 5}'])
    
    if result.exit_code != 0:
        print(f"FAILED OUTPUT:\n{result.stdout}")

    assert result.exit_code == 0
    assert "alice" in result.stdout

def test_e2e_calc_python():
    # This relies on examples.calc being importable
    result = runner.invoke(app, ["invoke", "calculate_tax", "--root", str(EXAMPLES_DIR), "--input", '{"amount": 100, "rate": 0.1}'])
    assert result.exit_code == 0
    # Output should be the float result 10.0
    assert "10.0" in result.stdout


def test_e2e_sha256_python(tmp_path):
    file_to_hash = tmp_path / "payload.txt"
    file_to_hash.write_text("brimley-test-payload", encoding="utf-8")
    expected = hashlib.sha256(b"brimley-test-payload").hexdigest()

    result = runner.invoke(
        app,
        [
            "invoke",
            "sha256_file",
            "--root",
            str(EXAMPLES_DIR),
            "--input",
            json.dumps({"filepath": str(file_to_hash)}),
        ],
    )

    assert result.exit_code == 0
    assert expected in result.stdout


def test_e2e_examples_discover_decorator_entity():
    scan_result = Scanner(EXAMPLES_DIR).scan()

    entity_names = {entity.name for entity in scan_result.entities}
    assert "User" in entity_names


def test_e2e_agent_sample_mockmcp_injection_runtime():
    scan_result = Scanner(EXAMPLES_DIR).scan()
    context = BrimleyContext()
    context.functions.register_all(scan_result.functions)
    context.entities.register_all(scan_result.entities)
    context.app["root_dir"] = str(EXAMPLES_DIR)

    mock_ctx = MockMCPContext(response_text="mocked-sample", model="mock-model")

    result = execute_function_by_name(
        context=context,
        function_name="agent_sample",
        input_data={"prompt": "hello"},
        runtime_injections={"mcp_context": mock_ctx},
    )

    assert result == "mocked-sample"


def test_e2e_examples_scanner_discovers_api_function():
    """github_profile.yaml is discovered as an api_function."""
    scan_result = Scanner(EXAMPLES_DIR).scan()
    api_funcs = {f.name for f in scan_result.functions if f.type == "api_function"}
    assert "get_github_profile" in api_funcs
    assert len(scan_result.diagnostics) == 0, scan_result.diagnostics


def test_e2e_examples_scanner_discovers_cli_function():
    """system_metrics.yaml is discovered as a cli_function."""
    scan_result = Scanner(EXAMPLES_DIR).scan()
    cli_funcs = {f.name for f in scan_result.functions if f.type == "cli_function"}
    assert "get_system_load" in cli_funcs
    assert len(scan_result.diagnostics) == 0, scan_result.diagnostics


def test_e2e_api_function_results_block_parsed():
    """github_profile.yaml results: block is parsed into ResultMapping objects."""
    from brimley.core.models import ApiFunction, ResultMapping

    scan_result = Scanner(EXAMPLES_DIR).scan()
    api_func = next(f for f in scan_result.functions if f.name == "get_github_profile")

    assert isinstance(api_func, ApiFunction)
    assert api_func.return_shape == "dict"
    assert api_func.results is not None

    ok_mapping = api_func.results.get("200")
    assert ok_mapping is not None
    assert ok_mapping.type == "json"
    # Empty path means return the full JSON profile payload.
    assert ok_mapping.parse == {"path": ""}

    err_mapping = api_func.results.get("404")
    assert err_mapping is not None
    assert "not found" in err_mapping.error.lower()


def test_e2e_cli_function_command_arguments_and_results_parsed():
    """system_metrics.yaml command_arguments and results: block parse correctly."""
    from brimley.core.models import CliFunction, ResultMapping

    scan_result = Scanner(EXAMPLES_DIR).scan()
    cli_func = next(f for f in scan_result.functions if f.name == "get_system_load")

    assert isinstance(cli_func, CliFunction)
    assert cli_func.command == "uptime"
    assert cli_func.command_arguments == []
    assert cli_func.timeout_seconds == 10.0
    assert cli_func.results is not None

    ok_mapping = cli_func.results.get("0")
    assert ok_mapping is not None
    assert ok_mapping.type == "regex"
    assert ok_mapping.parse is not None
    assert "load_1min" in ok_mapping.parse.get("capture_group", "")


# ---------------------------------------------------------------------------
# Helpers shared across invoke + REPL tests
# ---------------------------------------------------------------------------


def _make_github_http_mock() -> tuple[MagicMock, Any]:
    """Return (MockAsyncClient class, mock_response) for patching httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"login": "octocat", "name": "The Octocat"}
    mock_response.text = '{"login": "octocat", "name": "The Octocat"}'
    mock_response.content = mock_response.text.encode()
    mock_response.reason_phrase = "OK"

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    MockAsyncClient = MagicMock()
    MockAsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    MockAsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

    return MockAsyncClient, mock_response


# ---------------------------------------------------------------------------
# invoke — gap coverage (nested_greeting, get_system_load, greet_with_counter,
# get_github_profile were not previously tested via CLI invocation)
# ---------------------------------------------------------------------------


def test_e2e_nested_greeting_invoke():
    """nested_greeting composes hello internally — both must execute correctly."""
    result = runner.invoke(
        app,
        ["invoke", "nested_greeting", "--root", str(EXAMPLES_DIR), "--input", '{"name": "Composer"}'],
    )
    assert result.exit_code == 0, result.stdout
    assert "Composer" in result.stdout


def test_e2e_get_system_load_invoke():
    """get_system_load runs the uptime command and parses its output."""
    result = runner.invoke(
        app,
        ["invoke", "get_system_load", "--root", str(EXAMPLES_DIR), "--input", "{}"],
    )
    assert result.exit_code == 0, result.stdout
    assert result.stdout.strip()


def test_e2e_greet_with_counter_invoke():
    """Regression: Depends() param must not appear as a user arg; DI must inject it."""
    result = runner.invoke(
        app,
        ["invoke", "greet_with_counter", "--root", str(EXAMPLES_DIR), "--input", '{"name": "Alice"}'],
    )
    assert result.exit_code == 0, result.stdout
    assert "Alice" in result.stdout
    assert "invocation #1" in result.stdout


def test_e2e_get_github_profile_invoke():
    """get_github_profile executes via invoke with mocked HTTP."""
    MockAsyncClient, _ = _make_github_http_mock()
    with patch("httpx.AsyncClient", MockAsyncClient), \
         patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
        result = runner.invoke(
            app,
            [
                "invoke",
                "get_github_profile",
                "--root",
                str(EXAMPLES_DIR),
                "--input",
                '{"username": "octocat"}',
            ],
        )
    assert result.exit_code == 0, result.stdout
    assert "octocat" in result.stdout


# ---------------------------------------------------------------------------
# REPL-path tests
#
# BrimleyREPL.load() is the same code path the daemon uses.  Testing via an
# in-process BrimleyREPL instance (MCP disabled, no auto-reload) covers:
#   • config loading
#   • scanning + function registration
#   • DI startup (the bug that was just fixed)
#   • dispatch through the FastMCP synchronous code path (mock MCP context)
# ---------------------------------------------------------------------------


@pytest.fixture
def repl_session():
    """A freshly loaded BrimleyREPL for each test (function scope for isolation)."""
    from brimley.cli.repl import BrimleyREPL

    session = BrimleyREPL(
        EXAMPLES_DIR,
        mcp_enabled_override=False,
        auto_reload_enabled_override=False,
    )
    session.load()
    yield session
    if session.context.container is not None:
        try:
            session.context.container.shutdown()
        except Exception:
            pass


def _repl_exec(session: Any, func_name: str, input_data: dict) -> Any:  # noqa: ANN401
    """Execute a function through the REPL's dispatch path (mirrors handle_command)."""
    return execute_function_by_name(
        session.context,
        func_name,
        input_data,
        runtime_injections={"mcp_context": session.mock_mcp_context},
    )


# -- structural assertions --------------------------------------------------


def test_e2e_repl_load_initializes_di_container(repl_session):
    """load() must wire the DI container — the bug that triggered this work."""
    assert repl_session.context.container is not None


def test_e2e_repl_load_registers_expected_functions(repl_session):
    """All example functions are registered after load()."""
    registered = {f.name for f in repl_session.context.functions}
    expected = {
        "hello",
        "calculate_tax",
        "sha256_file",
        "nested_greeting",
        "agent_sample",
        "get_system_load",
        "get_github_profile",
        "greet_with_counter",
        "get_users",
    }
    assert expected.issubset(registered)


# -- per-function REPL execution tests --------------------------------------


def test_e2e_repl_hello_template(repl_session):
    result = _repl_exec(repl_session, "hello", {"name": "REPL"})
    assert "REPL" in result


def test_e2e_repl_calculate_tax(repl_session):
    result = _repl_exec(repl_session, "calculate_tax", {"amount": 100, "rate": 0.1})
    assert result == pytest.approx(10.0)


def test_e2e_repl_sha256_file(repl_session, tmp_path):
    target = tmp_path / "repl_test.txt"
    target.write_text("repl-hash-test", encoding="utf-8")
    expected = hashlib.sha256(b"repl-hash-test").hexdigest()
    result = _repl_exec(repl_session, "sha256_file", {"filepath": str(target)})
    assert result == expected


def test_e2e_repl_nested_greeting(repl_session):
    """nested_greeting (and its internal hello call) works through the REPL path."""
    result = _repl_exec(repl_session, "nested_greeting", {"name": "REPL"})
    assert "REPL" in result


def test_e2e_repl_agent_sample(repl_session):
    """agent_sample receives the MockMCPContext injected by the REPL dispatcher."""
    result = _repl_exec(repl_session, "agent_sample", {"prompt": "hello"})
    assert result is not None


def test_e2e_repl_get_system_load(repl_session):
    """get_system_load runs uptime through the REPL context."""
    result = _repl_exec(repl_session, "get_system_load", {})
    assert result is not None


def test_e2e_repl_greet_with_counter(repl_session):
    """Regression: Depends() resolves the RequestCounter through the REPL dispatch path."""
    result = _repl_exec(repl_session, "greet_with_counter", {"name": "REPL"})
    assert "REPL" in result
    assert "invocation #" in result


def test_e2e_repl_get_github_profile(repl_session):
    """API function executes via the REPL context with mocked HTTP."""
    MockAsyncClient, _ = _make_github_http_mock()
    with patch("httpx.AsyncClient", MockAsyncClient), \
         patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token"}):
        result = _repl_exec(repl_session, "get_github_profile", {"username": "octocat"})
    assert result is not None
    assert result.get("login") == "octocat"


