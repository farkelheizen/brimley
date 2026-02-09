import pytest
from brimley.execution.arguments import ArgumentResolver
from brimley.core.models import BrimleyFunction, TemplateFunction
from brimley.core.context import BrimleyContext

# -----------------------------------------------------------------------------
# Test Helpers
# -----------------------------------------------------------------------------

def create_func(args_def: dict) -> BrimleyFunction:
    """Helper to create a dummy function with specific args."""
    return TemplateFunction(
        name="test_func",
        type="template_function",
        return_shape="string",
        template_body="...",
        arguments=args_def
    )

@pytest.fixture
def context():
    ctx = BrimleyContext()
    ctx.app = {"user": {"id": "U123", "role": "admin"}}
    # Set a config value for testing
    # Note: Config is BaseSettings, usually read-only/env-based, 
    # but specific pydantic model might allow override if set on init, 
    # or we can mock property access if needed.
    return ctx

# -----------------------------------------------------------------------------
# 1. Shorthand Mode Tests
# -----------------------------------------------------------------------------

def test_resolve_shorthand_primitives(context):
    args_def = {
        "inline": {
            "count": "int",
            "name": "string",
            "active": "bool"
        }
    }
    func = create_func(args_def)
    
    user_input = {"count": 10, "name": "Brimley", "active": True}
    
    resolved = ArgumentResolver.resolve(func, user_input, context)
    
    assert resolved["count"] == 10
    assert resolved["name"] == "Brimley"
    assert resolved["active"] is True

def test_resolve_shorthand_casting(context):
    """Test loose casting (e.g. "10" -> 10)."""
    args_def = {"inline": {"count": "int"}}
    func = create_func(args_def)
    
    resolved = ArgumentResolver.resolve(func, {"count": "42"}, context)
    assert resolved["count"] == 42
    assert isinstance(resolved["count"], int)

def test_resolve_shorthand_missing_required(context):
    """Shorthand implies required by default (no default value specified)."""
    args_def = {"inline": {"needed": "string"}}
    func = create_func(args_def)
    
    with pytest.raises(ValueError, match="Missing required argument"):
        ArgumentResolver.resolve(func, {}, context)

# -----------------------------------------------------------------------------
# 2. Complex Mode Tests (Defaults)
# -----------------------------------------------------------------------------

def test_resolve_defaults(context):
    args_def = {
        "inline": {
            "limit": {"type": "int", "default": 20}
        }
    }
    func = create_func(args_def)
    
    # Case A: Use default
    res1 = ArgumentResolver.resolve(func, {}, context)
    assert res1["limit"] == 20
    
    # Case B: Override default
    res2 = ArgumentResolver.resolve(func, {"limit": 50}, context)
    assert res2["limit"] == 50

# -----------------------------------------------------------------------------
# 3. Context Injection Tests
# -----------------------------------------------------------------------------

def test_resolve_from_context_app(context):
    """Verify injection from context.app."""
    args_def = {
        "inline": {
            "user_id": {
                "type": "string",
                "from_context": "app.user.id"
            },
            "reason": "string"
        }
    }
    func = create_func(args_def)
    
    user_input = {"reason": "debugging"}
    resolved = ArgumentResolver.resolve(func, user_input, context)
    
    assert resolved["user_id"] == "U123"
    assert resolved["reason"] == "debugging"

def test_resolve_from_context_priority(context):
    """Context should override user input usually? 
    Or user input overrides context?
    The spec implies 'populated... instead of being provided'.
    Let's assume Context > User Input to enforce security.
    """
    args_def = {
        "inline": {
            "role": {
                "type": "string",
                "from_context": "app.user.role"
            }
        }
    }
    func = create_func(args_def)
    
    # User tries to spoof role
    user_input = {"role": "super-god"}
    resolved = ArgumentResolver.resolve(func, user_input, context)
    
    assert resolved["role"] == "admin" # Context wins

def test_resolve_from_context_missing_path(context):
    """If context path doesn't exist, it should error or be None?
    Strictness suggests error if required."""
    args_def = {
        "inline": {
            "gone": {"type": "string", "from_context": "app.missing.field"}
        }
    }
    func = create_func(args_def)
    
    with pytest.raises(ValueError, match="Context path 'app.missing.field' not found"):
        ArgumentResolver.resolve(func, {}, context)
