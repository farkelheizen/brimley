import os
import pytest
from brimley.core.context import BrimleyContext

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
