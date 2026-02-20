import ast
import importlib.util
from typer.testing import CliRunner

from brimley.cli.build import compile_assets
from brimley.cli.main import app
from brimley.core.models import SqlFunction, TemplateFunction
from brimley.discovery.runtime import scan_module


runner = CliRunner()


def _load_module_from_path(module_name: str, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_compile_assets_generates_valid_python_for_sql_files(tmp_path):
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

    result = compile_assets(tmp_path)
    content = result.output_file.read_text(encoding="utf-8")

    ast.parse(content)
    module = _load_module_from_path("generated_assets_sql", result.output_file)
    discovered = scan_module(module)
    sql_items = [item for item in discovered if isinstance(item, SqlFunction)]

    assert len(sql_items) == 1
    assert sql_items[0].name == "get_users"
    assert "SELECT * FROM users" in sql_items[0].sql_body


def test_scan_module_finds_functions_in_generated_assets_module(tmp_path):
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
    module = _load_module_from_path("generated_assets_mixed", result.output_file)
    discovered = scan_module(module)

    sql_items = [item for item in discovered if isinstance(item, SqlFunction)]
    template_items = [item for item in discovered if isinstance(item, TemplateFunction)]

    assert len(sql_items) == 1
    assert len(template_items) == 1
    assert sql_items[0].name == "get_users"
    assert template_items[0].name == "hello"


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
