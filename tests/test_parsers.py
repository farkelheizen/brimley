import pytest
import ast
from brimley.discovery.utils import parse_frontmatter
from brimley.discovery.sql_parser import parse_sql_file
from brimley.discovery.template_parser import parse_template_file
from brimley.discovery.python_parser import parse_python_file, _scan_for_reload_hazards
from brimley.core.models import DiscoveredEntity, SqlFunction, TemplateFunction, PythonFunction

# -----------------------------------------------------------------------------
# Utils: parse_frontmatter
# -----------------------------------------------------------------------------

def test_parse_frontmatter_markdown_style():
    content = """---
name: test_md
type: template_function
---
Hello {{ name }}
"""
    meta, body = parse_frontmatter(content)
    assert meta["name"] == "test_md"
    assert "Hello {{ name }}" in body.strip()

def test_parse_frontmatter_sql_style():
    content = """/*
---
name: test_sql
type: sql_function
---
*/
SELECT * FROM users
"""
    meta, body = parse_frontmatter(content)
    assert meta["name"] == "test_sql"
    assert "SELECT * FROM users" in body.strip()

def test_parse_frontmatter_no_frontmatter():
    content = "Just some text"
    meta, body = parse_frontmatter(content)
    assert meta == {}
    assert body == content

def test_parse_frontmatter_malformed_yaml():
    content = """---
name: test
  bad_indent: true
---
Body
"""
    with pytest.raises(ValueError, match="YAML"):
        parse_frontmatter(content)

# -----------------------------------------------------------------------------
# SQL Parser
# -----------------------------------------------------------------------------

def test_parse_sql_file(tmp_path):
    f = tmp_path / "query.sql"
    f.write_text("""/*
---
name: get_users
type: sql_function
connection: analytics
return_shape: void
---
*/
SELECT * FROM users
""")
    
    func = parse_sql_file(f)
    assert isinstance(func, SqlFunction)
    assert func.name == "get_users"
    assert func.connection == "analytics"
    assert "SELECT * FROM users" in func.sql_body

def test_parse_sql_file_missing_frontmatter(tmp_path):
    f = tmp_path / "bad.sql"
    # Even if valid SQL, if it's passed to parser, it expects frontmatter 
    # OR the scanner filter should have caught it. 
    # If the parser is called, it might fail validation if meta is missing.
    f.write_text("SELECT 1")
    
    with pytest.raises(ValueError, match="Validation error"):
         parse_sql_file(f)

def test_parse_sql_file_with_mcp_tool(tmp_path):
    f = tmp_path / "query.sql"
    f.write_text("""/*
---
name: get_users
type: sql_function
return_shape: void
mcp:
  type: tool
  description: SQL MCP tool
---
*/
SELECT * FROM users
""")

    func = parse_sql_file(f)
    assert isinstance(func, SqlFunction)
    assert func.mcp is not None
    assert func.mcp.type == "tool"

def test_parse_sql_file_rejects_invalid_mcp_metadata(tmp_path):
    f = tmp_path / "query.sql"
    f.write_text("""/*
---
name: get_users
type: sql_function
return_shape: void
mcp:
  type: resource
---
*/
SELECT * FROM users
""")

    with pytest.raises(ValueError, match="Validation error"):
        parse_sql_file(f)

# -----------------------------------------------------------------------------
# Template Parser
# -----------------------------------------------------------------------------

def test_parse_template_file(tmp_path):
    f = tmp_path / "greet.md"
    f.write_text("""---
name: greet_user
type: template_function
return_shape: string
---
Hello {{ args.name }}
""")
    
    func = parse_template_file(f)
    assert isinstance(func, TemplateFunction)
    assert func.name == "greet_user"
    assert "Hello {{ args.name }}" in func.template_body

def test_parse_template_file_with_mcp_tool(tmp_path):
    f = tmp_path / "greet.md"
    f.write_text("""---
name: greet_user
type: template_function
return_shape: string
mcp:
  type: tool
---
Hello {{ args.name }}
""")

    func = parse_template_file(f)
    assert isinstance(func, TemplateFunction)
    assert func.mcp is not None
    assert func.mcp.type == "tool"

def test_parse_template_file_rejects_invalid_mcp_metadata(tmp_path):
    f = tmp_path / "greet.md"
    f.write_text("""---
name: greet_user
type: template_function
return_shape: string
mcp:
  type: resource
---
Hello {{ args.name }}
""")

    with pytest.raises(ValueError, match="Validation error"):
        parse_template_file(f)

# -----------------------------------------------------------------------------
# Python Parser
# -----------------------------------------------------------------------------

def test_parse_python_file_decorator_infers_module_handler(tmp_path, monkeypatch):
    root = tmp_path / "project"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")

    f = pkg / "logic.py"
    f.write_text('''from brimley import function

@function
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    monkeypatch.syspath_prepend(str(root))
    parsed = parse_python_file(f)

    assert len(parsed) == 1
    func = parsed[0]
    assert isinstance(func, PythonFunction)
    assert func.name == "calculate_tax"
    assert func.handler == "pkg.logic.calculate_tax"
    assert func.return_shape == "float"


def test_parse_python_file_decorator_with_mcp_tool_and_reload(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''from brimley import function

@function(name="calculate_tax", mcpType="tool", reload=False)
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    parsed = parse_python_file(f)

    assert len(parsed) == 1
    func = parsed[0]
    assert isinstance(func, PythonFunction)
    assert func.name == "calculate_tax"
    assert func.reload is False
    assert func.mcp is not None
    assert func.mcp.type == "tool"


def test_parse_python_file_supports_qualified_decorator_name(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''import brimley

@brimley.function
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    parsed = parse_python_file(f)

    assert len(parsed) == 1
    func = parsed[0]
    assert isinstance(func, PythonFunction)
    assert func.handler == "logic.calculate_tax"


def test_parse_python_file_parses_python_entity_class(tmp_path):
    f = tmp_path / "models.py"
    f.write_text('''from brimley import entity

@entity
class User:
    pass
''')

    parsed = parse_python_file(f)

    assert len(parsed) == 1
    item = parsed[0]
    assert isinstance(item, DiscoveredEntity)
    assert item.name == "User"
    assert item.type == "python_entity"
    assert item.handler == "models.User"


def test_parse_python_file_parses_mixed_functions_and_entities(tmp_path):
    f = tmp_path / "bundle.py"
    f.write_text('''from brimley import function, entity

@entity
class User:
    pass

@function
def get_user(user_id: int) -> dict:
    return {"id": user_id}
''')

    parsed = parse_python_file(f)

    assert len(parsed) == 2
    function_items = [item for item in parsed if isinstance(item, PythonFunction)]
    entity_items = [item for item in parsed if isinstance(item, DiscoveredEntity)]

    assert len(function_items) == 1
    assert len(entity_items) == 1


def test_parse_python_file_infers_handler_and_arguments_for_legacy_frontmatter(tmp_path, monkeypatch):
    root = tmp_path / "project"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")

    f = pkg / "legacy.py"
    f.write_text('''"""
---
name: summarize
type: python_function
return_shape: string
---
"""
def summarize(name: str, retries: int = 2, enabled: bool = True) -> str:
    return name
''')

    monkeypatch.syspath_prepend(str(root))
    parsed = parse_python_file(f)

    assert len(parsed) == 1
    func = parsed[0]
    assert isinstance(func, PythonFunction)
    assert func.handler == "pkg.legacy.summarize"
    assert func.arguments is not None
    assert func.arguments["inline"] == {
        "name": "string",
        "retries": {"type": "int", "default": 2},
        "enabled": {"type": "bool", "default": True},
    }


def test_parse_python_file_annotated_appstate_and_config_mark_from_context(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''from typing import Annotated
from brimley import function, AppState, Config

@function
def agent_tool(
    prompt: str,
    session_id: Annotated[str, AppState("session_id")],
    app_name: Annotated[str, Config("app_name")],
) -> str:
    return prompt
''')

    parsed = parse_python_file(f)

    assert len(parsed) == 1
    func = parsed[0]
    assert isinstance(func, PythonFunction)
    inline = func.arguments["inline"]

    assert inline["prompt"] == "string"
    assert inline["session_id"]["from_context"] == "app.session_id"
    assert inline["app_name"]["from_context"] == "config.app_name"


def test_parse_python_file_omits_injected_context_type_arguments(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''from brimley import function
from brimley.core.context import BrimleyContext

class MockMCPContext:
    pass

class Context:
    pass

@function
def agent_tool(prompt: str, ctx: BrimleyContext, mcp_ctx: Context, fake: MockMCPContext, count: int = 1) -> str:
    return prompt
''')

    parsed = parse_python_file(f)

    assert len(parsed) == 1
    func = parsed[0]
    assert isinstance(func, PythonFunction)

    inline = func.arguments["inline"]
    assert "prompt" in inline
    assert "count" in inline
    assert "ctx" not in inline
    assert "mcp_ctx" not in inline
    assert "fake" not in inline


def test_parse_python_file_rejects_unsupported_decorator_function_type(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''from brimley import function

@function(type="sql_function")
def query() -> str:
    return "SELECT 1"
''')

    with pytest.raises(ValueError, match="Unsupported decorated function type"):
        parse_python_file(f)


def test_parse_python_file_returns_empty_for_no_decorator_or_legacy_frontmatter(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    parsed = parse_python_file(f)
    assert parsed == []


def test_scan_for_reload_hazards_detects_top_level_side_effect_calls_when_reload_enabled():
    tree = ast.parse(
        '''from brimley import function

open("file.txt", "w")

@function
def greet() -> str:
    return "ok"
'''
    )

    hazards = _scan_for_reload_hazards(tree)

    assert len(hazards) == 1
    assert "open" in hazards[0]


def test_scan_for_reload_hazards_ignores_top_level_calls_when_reload_disabled():
    tree = ast.parse(
        '''from brimley import function

open("file.txt", "w")

@function(reload=False)
def greet() -> str:
    return "ok"
'''
    )

    hazards = _scan_for_reload_hazards(tree)

    assert hazards == []


def test_scan_for_reload_hazards_detects_attribute_calls():
    tree = ast.parse(
        '''from brimley import function
import subprocess

subprocess.Popen(["echo", "hi"])

@function(reload=True)
def greet() -> str:
    return "ok"
'''
    )

    hazards = _scan_for_reload_hazards(tree)

    assert len(hazards) == 1
    assert "Popen" in hazards[0]


def test_scan_for_reload_hazards_ignores_when_no_decorated_functions():
    tree = ast.parse(
        '''open("file.txt", "w")

def greet() -> str:
    return "ok"
'''
    )

    hazards = _scan_for_reload_hazards(tree)

    assert hazards == []
