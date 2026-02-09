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
    
    # Args are passed as a dictionary where key 'args' holds the user args
    # Wait, spec check: How are args exposed in template? 
    # Usually `{{ name }}` or `{{ args.name }}`.
    # Looking at `brimley-template-functions.md`: `{{ args.genre }}`.
    # So the context passed to jinja should have `args`.
    
    result = runner.run(func, {"name": "World"}, context)
    assert result == "Hello World!"

def test_jinja_render_void_return(runner, context):
    # If return_shape is void (unlikely for template, but possible?)
    # Usually template returns string.
    pass

def test_jinja_parsing_messages(runner, context):
    """
    If return_shape is 'PromptMessage[]' (or similar), 
    the runner might need to parse the output string into messages.
    Current step P3-S2 says 'Implement Jinja2 rendering'.
    Parsing messages might be part of this or separate utility.
    Let's test simple string rendering first as per plan.
    """
    pass

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
