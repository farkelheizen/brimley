import pytest
from typer.testing import CliRunner
from brimley.cli.main import app

def test_diagnostics_table(tmp_path):
    runner = CliRunner()
    
    # Create a bad function file (missing name)
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "bad.md"
    f.write_text("""---
type: template_function
# name is missing
return_shape: string
---
Body""")

    # Run check
    # mix_stderr=False needed to check stderr specifically? 
    # Typer runner captures both.
    
    result = runner.invoke(app, ["invoke", "bad", "--root", str(tmp_path / "funcs")])
    
    # We expect failure
    assert result.exit_code == 1
    
    # Check for Rich Table elements
    # Since mixed env, it should be in stdout
    # Look for table title
    assert "Brimley Diagnostics" in result.stdout
    # Look for validation error hint
    assert "ERR_PARSE_FAILURE" in result.stdout or "Validation error" in result.stdout
