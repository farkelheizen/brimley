import pytest
import json
import sys
import hashlib
from pathlib import Path
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
