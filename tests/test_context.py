import os
import pytest
from brimley.core.context import BrimleyContext
from brimley.execution import execute_helper

def test_context_initialization_defaults():
    """Verify Context loads with empty state and default config."""
    # Ensure no env vars interfere
    if "BRIMLEY_ENV" in os.environ:
        del os.environ["BRIMLEY_ENV"]
        
    ctx = BrimleyContext()
    
    # App state should be empty dict
    assert ctx.app == {}
    
    # Config should be present (even if empty/defaults)
    assert ctx.config is not None
    assert ctx.settings.env == "development" # Default

def test_context_config_from_env():
    """Verify Config loads from environment variables."""
    os.environ["BRIMLEY_ENV"] = "production"
    os.environ["BRIMLEY_APP_NAME"] = "TestApp"
    
    try:
        # Re-initialize to pick up env vars
        ctx = BrimleyContext()
        assert ctx.settings.env == "production"
        assert ctx.settings.app_name == "TestApp"
    finally:
        # Cleanup
        del os.environ["BRIMLEY_ENV"]
        del os.environ["BRIMLEY_APP_NAME"]

def test_app_state_mutability():
    """Verify 'app' is mutable and persists state."""
    ctx = BrimleyContext()
    ctx.app["counter"] = 1
    assert ctx.app["counter"] == 1
    
    ctx.app["counter"] += 1
    assert ctx.app["counter"] == 2

def test_context_registries_initialization():
    """Verify 'databases' and 'functions' and 'entities' registries exist."""
    ctx = BrimleyContext()
    # Now they are Registry objects
    assert len(ctx.functions) == 0
    assert ctx.databases == {}
    
    # Entities should have built-ins
    assert "ContentBlock" in ctx.entities
    assert "PromptMessage" in ctx.entities
    
    from brimley.core.entity import ContentBlock, PromptMessage
    assert ctx.entities.get("ContentBlock") == ContentBlock
    assert ctx.entities.get("PromptMessage") == PromptMessage


def test_context_execute_function_by_name_delegates_to_helper(monkeypatch: pytest.MonkeyPatch):
    ctx = BrimleyContext()
    runtime_injections = {"mcp_context": object()}
    captured = {}

    def fake_execute_function_by_name(context, function_name, input_data, runtime_injections=None):
        captured["context"] = context
        captured["function_name"] = function_name
        captured["input_data"] = input_data
        captured["runtime_injections"] = runtime_injections
        return {"ok": True}

    monkeypatch.setattr(execute_helper, "execute_function_by_name", fake_execute_function_by_name)

    result = ctx.execute_function_by_name(
        function_name="child_task",
        input_data={"name": "Ada"},
        runtime_injections=runtime_injections,
    )

    assert result == {"ok": True}
    assert captured["context"] is ctx
    assert captured["function_name"] == "child_task"
    assert captured["input_data"] == {"name": "Ada"}
    assert captured["runtime_injections"] is runtime_injections
