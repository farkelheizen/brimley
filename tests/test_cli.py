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
