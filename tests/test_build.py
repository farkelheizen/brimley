from typer.testing import CliRunner

from brimley.cli.build import compile_assets
from brimley.cli.main import app


runner = CliRunner()


def test_compile_assets_generates_sql_and_template_shims(tmp_path):
    (tmp_path / "query.sql").write_text(
        """/*
---
name: get_users
type: sql_function
connection: analytics
return_shape: list[dict]
---
*/
SELECT * FROM users
"""
    )

    (tmp_path / "hello.md").write_text(
        """---
name: hello
type: template_function
return_shape: string
---
Hello {{ args.name }}
"""
    )

    result = compile_assets(tmp_path)
    content = result.output_file.read_text(encoding="utf-8")

    assert result.output_file == tmp_path / "brimley_assets.py"
    assert result.sql_functions == 1
    assert result.template_functions == 1
    assert "@function(name='get_users', type='sql_function'" in content
    assert "content='SELECT * FROM users" in content
    assert "@function(name='hello', type='template_function'" in content
    assert "content='Hello {{ args.name }}" in content


def test_compile_assets_writes_no_assets_stub_when_none_found(tmp_path):
    (tmp_path / "notes.txt").write_text("nothing")

    result = compile_assets(tmp_path)
    content = result.output_file.read_text(encoding="utf-8")

    assert result.sql_functions == 0
    assert result.template_functions == 0
    assert "No SQL or template assets discovered" in content


def test_build_cli_generates_custom_output_file(tmp_path):
    (tmp_path / "query.sql").write_text(
        """/*
---
name: get_users
type: sql_function
return_shape: list[dict]
---
*/
SELECT * FROM users
"""
    )

    output_file = tmp_path / "generated" / "brimley_assets.py"
    cli_result = runner.invoke(
        app,
        ["build", "--root", str(tmp_path), "--output", str(output_file)],
    )

    assert cli_result.exit_code == 0
    assert output_file.exists()
    assert "Generated assets at" in (cli_result.stdout + getattr(cli_result, "stderr", ""))
