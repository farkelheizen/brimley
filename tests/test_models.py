import pytest
from pydantic import ValidationError
from brimley.core.models import (
    BrimleyFunction, 
    DiscoveredEntity,
    PythonFunction, 
    SqlFunction, 
    TemplateFunction,
    AutoReloadSettings,
)
from brimley.core.entity import PromptMessage

# -----------------------------------------------------------------------------
# Base Function Tests
# -----------------------------------------------------------------------------

def test_base_function_requires_name_and_type():
    """Verify name and type are mandatory."""
    # Should fail missing fields
    with pytest.raises(ValidationError):
        BrimleyFunction(name="test")
    
    with pytest.raises(ValidationError):
        BrimleyFunction(type="some_type")

    # Should pass
    bf = BrimleyFunction(name="my_func", type="custom", return_shape="string")
    assert bf.name == "my_func"

def test_return_shape_polymorphism():
    """Verify return_shape can be string or dict."""
    f1 = BrimleyFunction(name="f1", type="t", return_shape="string")
    assert f1.return_shape == "string"

    f2 = BrimleyFunction(name="f2", type="t", return_shape={"type": "object"})
    assert f2.return_shape == {"type": "object"}

def test_function_accepts_mcp_tool_config():
    """Verify mcp metadata accepts type=tool and optional description."""
    func = BrimleyFunction(
        name="mcp_ready",
        type="template_function",
        return_shape="string",
        mcp={"type": "tool", "description": "Tool-specific summary"},
    )

    assert func.mcp is not None
    assert func.mcp.type == "tool"
    assert func.mcp.description == "Tool-specific summary"

def test_function_rejects_invalid_mcp_type():
    """Verify mcp.type only allows 'tool'."""
    with pytest.raises(ValidationError):
        BrimleyFunction(
            name="bad_mcp_type",
            type="template_function",
            return_shape="string",
            mcp={"type": "resource"},
        )

def test_function_rejects_invalid_mcp_shape():
    """Verify unsupported keys in mcp metadata are rejected."""
    with pytest.raises(ValidationError):
        BrimleyFunction(
            name="bad_mcp_shape",
            type="template_function",
            return_shape="string",
            mcp={"type": "tool", "x": "unsupported"},
        )

def test_function_mcp_round_trip_model_dump():
    """Verify MCP metadata survives model dump/load round-trip."""
    original = BrimleyFunction(
        name="round_trip",
        type="template_function",
        return_shape="string",
        mcp={"type": "tool", "description": "Round trip"},
    )

    dumped = original.model_dump()
    hydrated = BrimleyFunction(**dumped)

    assert hydrated.mcp is not None
    assert hydrated.mcp.type == "tool"
    assert hydrated.mcp.description == "Round trip"

# -----------------------------------------------------------------------------
# Python Function Tests
# -----------------------------------------------------------------------------

def test_python_function_properties():
    """Verify PythonFunction specific fields."""
    pf = PythonFunction(
        name="py_logic",
        type="python_function",
        handler="pkg.mod.func",
        return_shape="void"
    )
    assert pf.handler == "pkg.mod.func"
    assert pf.type == "python_function"


def test_python_function_reload_defaults_true():
    pf = PythonFunction(
        name="reload_default",
        type="python_function",
        handler="pkg.mod.func",
        return_shape="void",
    )

    assert pf.reload is True


def test_python_function_reload_can_be_disabled():
    pf = PythonFunction(
        name="reload_disabled",
        type="python_function",
        handler="pkg.mod.func",
        return_shape="void",
        reload=False,
    )

    assert pf.reload is False

def test_python_function_type_validator():
    """Verify type must be 'python_function'."""
    with pytest.raises(ValidationError):
        PythonFunction(name="bad", type="sql_function", handler="x", return_shape="void")

# -----------------------------------------------------------------------------
# SQL Function Tests
# -----------------------------------------------------------------------------

def test_sql_function_defaults():
    """Verify SqlFunction defaults."""
    sf = SqlFunction(
        name="get_users",
        type="sql_function",
        sql_body="SELECT * FROM users",
        return_shape="void"
    )
    assert sf.connection == "default"
    assert sf.sql_body == "SELECT * FROM users"

def test_sql_function_custom_connection():
    sf = SqlFunction(
        name="get_logs",
        type="sql_function",
        sql_body="SELECT 1",
        connection="analytics",
        return_shape="void"
    )
    assert sf.connection == "analytics"

# -----------------------------------------------------------------------------
# Template Function Tests
# -----------------------------------------------------------------------------

def test_template_function_defaults():
    """Verify TemplateFunction defaults."""
    tf = TemplateFunction(
        name="greet",
        type="template_function",
        template_body="Hello {{ name }}",
        return_shape="string"
    )
    assert tf.template_engine == "jinja2"
    assert tf.template_body == "Hello {{ name }}"
    assert tf.messages is None

def test_template_function_inline_messages():
    """Verify TemplateFunction with structured messages."""
    msg = PromptMessage(role="user", content="Hi")
    tf = TemplateFunction(
        name="chat",
        type="template_function",
        messages=[msg],
        return_shape="PromptMessage[]"
    )
    assert len(tf.messages) == 1
    assert tf.messages[0].role == "user"


def test_auto_reload_settings_defaults():
    """Verify auto-reload defaults align with the configuration contract."""
    settings = AutoReloadSettings()
    assert settings.enabled is False
    assert settings.interval_ms == 1000
    assert settings.debounce_ms == 300
    assert settings.include_patterns == ["*.py", "*.sql", "*.md", "*.yaml"]
    assert settings.exclude_patterns == []


def test_auto_reload_settings_interval_minimum_enforced():
    """Verify interval lower bound is validated."""
    with pytest.raises(ValidationError):
        AutoReloadSettings(interval_ms=99)


def test_discovered_entity_supports_python_entity_type_and_handler():
    entity = DiscoveredEntity(
        name="User",
        type="python_entity",
        handler="pkg.models.User",
    )

    assert entity.name == "User"
    assert entity.type == "python_entity"
    assert entity.handler == "pkg.models.User"


def test_discovered_entity_defaults_to_legacy_entity_type():
    entity = DiscoveredEntity(name="LegacyEntity")

    assert entity.type == "entity"
    assert entity.handler is None
