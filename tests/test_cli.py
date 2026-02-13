import pytest
import json
from typer.testing import CliRunner
from brimley.cli.main import app
from pathlib import Path

runner = CliRunner()

def test_invoke_help():
    result = runner.invoke(app, ["invoke", "--help"])
    assert result.exit_code == 0
    assert "Invoke a Brimley function" in result.stdout

def test_invoke_missing_function():
    result = runner.invoke(app, ["invoke", "non_existent_func"])
    assert result.exit_code == 1
    # CliRunner default is to mix stderr into stdout
    assert "Function 'non_existent_func' not found" in result.stdout

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
    assert "Invalid YAML" in result.stdout

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


def test_repl_flag_mcp_enables_embedded(monkeypatch, tmp_path):
    captured = {}

    class DummyREPL:
        def __init__(self, root_dir, mcp_enabled_override=None):
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
        def __init__(self, root_dir, mcp_enabled_override=None):
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
        def __init__(self, root_dir, mcp_enabled_override=None):
            captured["root_dir"] = root_dir
            captured["override"] = mcp_enabled_override

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("brimley.cli.main.BrimleyREPL", DummyREPL)

    result = runner.invoke(app, ["repl", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["override"] is None
    assert captured["started"] is True
