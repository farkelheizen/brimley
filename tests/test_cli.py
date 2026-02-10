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
select * from users where id = {{ args.id }}
""")
    
    result = runner.invoke(app, ["invoke", "get_users", 
                                 "--root", str(tmp_path / "sql"), 
                                 "--input", '{"id": 123}'])
    
    if result.exit_code != 0:
        print(f"FAILED OUTPUT:\n{result.stdout}")

    assert result.exit_code == 0
    # Verify we got JSON back (check keys)
    # CliRunner mixes stdout/stderr by default, so strict json.loads fails if runners log to stderr
    assert '"function": "get_users"' in result.stdout
    assert '"connection": "default"' in result.stdout
    assert '"mock_data": []' in result.stdout
    assert "select * from users" in result.stdout
