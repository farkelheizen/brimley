import pytest
from brimley.discovery.utils import parse_frontmatter
from brimley.discovery.sql_parser import parse_sql_file
from brimley.discovery.template_parser import parse_template_file
from brimley.discovery.python_parser import parse_python_file
from brimley.core.models import SqlFunction, TemplateFunction, PythonFunction

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

def test_parse_python_file_infers_module_handler(tmp_path, monkeypatch):
    root = tmp_path / "project"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")

    f = pkg / "logic.py"
    f.write_text('''"""
---
name: calculate_tax
type: python_function
handler: calculate_tax
return_shape: float
---
"""
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    monkeypatch.syspath_prepend(str(root))
    func = parse_python_file(f)

    assert func.handler == "pkg.logic.calculate_tax"

def test_parse_python_file_preserves_dotted_handler(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''"""
---
name: calculate_tax
type: python_function
handler: custom.module.calculate_tax
return_shape: float
---
"""
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    func = parse_python_file(f)
    assert func.handler == "custom.module.calculate_tax"

def test_parse_python_file_with_mcp_tool(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''"""
---
name: calculate_tax
type: python_function
handler: custom.module.calculate_tax
return_shape: float
mcp:
  type: tool
---
"""
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    func = parse_python_file(f)
    assert isinstance(func, PythonFunction)
    assert func.mcp is not None
    assert func.mcp.type == "tool"

def test_parse_python_file_rejects_invalid_mcp_metadata(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''"""
---
name: calculate_tax
type: python_function
handler: custom.module.calculate_tax
return_shape: float
mcp:
  type: resource
---
"""
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
''')

    with pytest.raises(ValueError, match="Validation error"):
        parse_python_file(f)


def test_parse_python_file_infers_inline_arguments_from_handler_signature(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''"""
---
name: summarize
type: python_function
handler: summarize
return_shape: string
---
"""
def summarize(name: str, retries: int = 2, enabled: bool = True) -> str:
    return name
''')

    func = parse_python_file(f)

    assert func.arguments is not None
    assert "inline" in func.arguments
    assert func.arguments["inline"] == {
        "name": "string",
        "retries": {"type": "int", "default": 2},
        "enabled": {"type": "bool", "default": True},
    }


def test_parse_python_file_omits_injected_context_typed_arguments(tmp_path):
    f = tmp_path / "logic.py"
    f.write_text('''"""
---
name: agent_tool
type: python_function
handler: agent_tool
return_shape: string
---
"""
from brimley.core.context import BrimleyContext
from mcp.server.fastmcp import Context

def agent_tool(prompt: str, ctx: BrimleyContext, mcp_ctx: Context, count: int = 1) -> str:
    return prompt
''')

    func = parse_python_file(f)

    assert func.arguments is not None
    inline = func.arguments["inline"]
    assert "prompt" in inline
    assert "count" in inline
    assert "ctx" not in inline
    assert "mcp_ctx" not in inline
