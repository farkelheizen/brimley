import pytest
from brimley.execution.jinja_runner import JinjaRunner
from brimley.core.models import TemplateFunction
from brimley.core.context import BrimleyContext

@pytest.fixture
def runner():
    return JinjaRunner()

@pytest.fixture
def context():
    return BrimleyContext()

def test_jinja_render_simple_string(runner, context):
    func = TemplateFunction(
        name="greet",
        type="template_function",
        return_shape="string",
        template_body="Hello {{ args.name }}!"
    )
    
    # templates access variables via the 'args' namespace
    result = runner.run(func, {"name": "World"}, context)
    assert result == "Hello World!"

def test_jinja_cannot_access_context_directly(runner, context):
    """
    Constraint: Templates must NOT be able to access the global context directly.
    """
    context.config.app_name = "SecretApp"
    
    func = TemplateFunction(
        name="security_test",
        type="template_function",
        return_shape="string",
        # Attempt to access context directly
        template_body="App: {{ context.config.app_name }}" 
    )
    
    # Since 'context' is not passed to Jinja, it treats it as an undefined variable.
    # Default Jinja behavior for Undefined raises error on attribute access (context.config).
    # This confirms context is not available.
    from jinja2.exceptions import UndefinedError
    with pytest.raises(UndefinedError):
        runner.run(func, {}, context)
    
    # Alternatively, if we just accessed {{ context }}, it would be empty string.
    func2 = TemplateFunction(
        name="security_test_2",
        type="template_function",
        return_shape="string",
        template_body="App: {{ context }}" 
    )
    result = runner.run(func2, {}, context)
    assert result == "App: "

def test_jinja_render_with_resolved_args(runner, context):
    """
    Demonstrate the 'Correct Way': 
    The ArgumentResolver (not tested here) would have already extracted 
    values from the context and put them into the resolved_args dictionary.
    """
    # Simulate ArgumentResolver output
    resolved_args = {
        "app_name": "BrimleyApp", 
        "user_id": 101
    }
    
    func = TemplateFunction(
        name="correct_way",
        type="template_function",
        return_shape="string",
        template_body="Welcome to {{ args.app_name }}, User {{ args.user_id }}."
    )
    
    result = runner.run(func, resolved_args, context)
    assert result == "Welcome to BrimleyApp, User 101."

def test_jinja_missing_variable(runner, context):
    """Jinja defaults to empty string for missing vars usually, unless strict."""
    func = TemplateFunction(
        name="missing", 
        type="template_function", 
        return_shape="p",
        template_body="Hi {{ args.missing }}"
    )
    # Default jinja behavior is non-strict
    result = runner.run(func, {}, context) # missing 'missing' arg
    assert result == "Hi "