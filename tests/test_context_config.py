import pytest
from pydantic import ValidationError

from brimley.core.context import BrimleyContext

def test_context_init_with_config():
    config_data = {
        "brimley": {
            "app_name": "Test App",
            "env": "test"
        },
        "config": {
            "api_key": "123",
            "feature_x": True
        },
        "mcp": {
            "embedded": False,
            "transport": "stdio",
            "host": "0.0.0.0",
            "port": 9001,
        },
        "auto_reload": {
            "enabled": True,
            "interval_ms": 1500,
            "debounce_ms": 500,
            "include_patterns": ["*.py", "*.sql"],
            "exclude_patterns": [".venv/*"],
        },
        "state": {
            "user": "admin"
        }
    }
    
    ctx = BrimleyContext(config_dict=config_data)
    
    assert ctx.settings.app_name == "Test App"
    assert ctx.settings.env == "test"
    assert ctx.config.api_key == "123" # Pydantic extra='allow'
    assert getattr(ctx.config, "feature_x") is True
    assert ctx.mcp.embedded is False
    assert ctx.mcp.transport == "stdio"
    assert ctx.mcp.host == "0.0.0.0"
    assert ctx.mcp.port == 9001
    assert ctx.auto_reload.enabled is True
    assert ctx.auto_reload.interval_ms == 1500
    assert ctx.auto_reload.debounce_ms == 500
    assert ctx.auto_reload.include_patterns == ["*.py", "*.sql"]
    assert ctx.auto_reload.exclude_patterns == [".venv/*"]
    assert ctx.app["user"] == "admin"

def test_context_default_init():
    ctx = BrimleyContext()
    assert ctx.settings.app_name == "Brimley App"
    assert ctx.mcp.embedded is True
    assert ctx.mcp.transport == "sse"
    assert ctx.mcp.host == "127.0.0.1"
    assert ctx.mcp.port == 8000
    assert ctx.auto_reload.enabled is False
    assert ctx.auto_reload.interval_ms == 1000
    assert ctx.auto_reload.debounce_ms == 300
    assert ctx.auto_reload.include_patterns == ["*.py", "*.sql", "*.md", "*.yaml"]
    assert ctx.auto_reload.exclude_patterns == []
    assert ctx.app == {}


def test_context_auto_reload_partial_config_applies_defaults():
    ctx = BrimleyContext(config_dict={"auto_reload": {"enabled": True}})

    assert ctx.auto_reload.enabled is True
    assert ctx.auto_reload.interval_ms == 1000
    assert ctx.auto_reload.debounce_ms == 300
    assert ctx.auto_reload.include_patterns == ["*.py", "*.sql", "*.md", "*.yaml"]
    assert ctx.auto_reload.exclude_patterns == []


def test_context_auto_reload_invalid_interval_raises_validation_error():
    with pytest.raises(ValidationError):
        BrimleyContext(config_dict={"auto_reload": {"interval_ms": 99}})
