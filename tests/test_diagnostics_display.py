import pytest
from typer.testing import CliRunner
from brimley.cli.main import app
from brimley.cli.formatter import OutputFormatter
from brimley.core.context import RuntimeErrorRecord


def _combined_output(result) -> str:
    return f"{result.stdout}{getattr(result, 'stderr', '')}"

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
    output = _combined_output(result)
    assert "Brimley Diagnostics" in output
    # Look for validation error hint
    assert "ERR_PARSE_FAILURE" in output or "Validation error" in output


def test_runtime_errors_table_includes_expected_columns(capsys):
    records = [
        RuntimeErrorRecord(
            key="broken.md|ERR_PARSE_FAILURE|bad frontmatter||error",
            object_name="broken",
            error_class="ERR_PARSE_FAILURE",
            severity="error",
            message="bad frontmatter",
            file_path="broken.md",
            line_number=7,
            source="reload",
            status="active",
            first_seen_index=1,
            last_seen_index=3,
            resolved_at_index=None,
        )
    ]

    OutputFormatter.print_runtime_errors(records, total=1, limit=50, offset=0, include_history=False)

    captured = capsys.readouterr()
    combined = f"{captured.out}{captured.err}"
    assert "Brimley Runtime Errors" in combined
    assert "Object" in combined
    assert "Error Class" in combined
    assert "bad frontmatter" in combined
    assert "broken.md:7" in combined
