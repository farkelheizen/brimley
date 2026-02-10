import pytest
import json
import sys
from pathlib import Path
from typer.testing import CliRunner
from brimley.cli.main import app

runner = CliRunner()
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Ensure we can import from examples logic
sys.path.append(str(EXAMPLES_DIR.parent))

def test_e2e_hello_template():
    result = runner.invoke(app, ["invoke", "hello", "--root", str(EXAMPLES_DIR), "--input", '{"name": "E2E"}'])
    assert result.exit_code == 0
    assert "Hello E2E!" in result.stdout

def test_e2e_users_sql():
    result = runner.invoke(app, ["invoke", "get_users", "--root", str(EXAMPLES_DIR), "--input", '{"limit": 5}'])
    assert result.exit_code == 0
    assert '"function": "get_users"' in result.stdout
    assert '"limit": 5' in result.stdout

def test_e2e_calc_python():
    # This relies on examples.calc being importable
    result = runner.invoke(app, ["invoke", "calculate_tax", "--root", str(EXAMPLES_DIR), "--input", '{"amount": 100, "rate": 0.1}'])
    assert result.exit_code == 0
    # Output should be the float result 10.0
    assert "10.0" in result.stdout
