import pytest
from unittest.mock import MagicMock, ANY
from brimley.mcp.adapter import BrimleyMCPAdapter

# Mock objects to simulate Brimley and FastMCP
class MockToolArg:
    def __init__(self, name, type_str, required=True, default=None):
        self.name = name
        self.type = type_str
        self.required = required
        self.default = default

class MockToolDef:
    def __init__(self, description, args):
        self.description = description
        self.arguments = MagicMock()
        self.arguments.inline = args

class MockBrimleyEngine:
    def __init__(self):
        self._tools = {}
    
    def execute_tool(self, name, args):
        return f"Executed {name} with {args}"

def test_adapter_registration():
    # 1. Setup Mocks
    engine = MockBrimleyEngine()
    
    # Define a tool: "add_numbers(x: int, y: int = 10)"
    tool_def = MockToolDef(
        description="Adds two numbers",
        args=[
            MockToolArg("x", "int", required=True),
            MockToolArg("y", "int", required=False, default=10)
        ]
    )
    engine._tools["add_numbers"] = tool_def
    
    # Mock FastMCP
    mcp_server = MagicMock()
    # mcp.tool(...) returns a decorator, which is called with the function
    mcp_decorator = MagicMock()
    mcp_server.tool.return_value = mcp_decorator
    
    # 2. Init Adapter
    adapter = BrimleyMCPAdapter(engine, mcp_server)
    
    # 3. Run Registration
    count = adapter.register_tools()
    
    # 4. Assertions
    assert count == 1
    
    # Verify mcp.tool was called with correct metadata
    mcp_server.tool.assert_called_once_with(
        name="add_numbers",
        description="Adds two numbers"
    )
    
    # Verify the decorator was called (which registers the function)
    mcp_decorator.assert_called_once()
    
    # Get the generated function from the decorator call
    generated_func = mcp_decorator.call_args[0][0]
    
    # 5. Verify the generated function's properties
    assert generated_func.__name__ == "add_numbers"
    assert "Adds two numbers" in generated_func.__doc__
    
    # Verify signature annotations (tricky with exec, but we can check inspection)
    import inspect
    sig = inspect.signature(generated_func)
    assert "x" in sig.parameters
    assert sig.parameters["x"].annotation == int
    assert "y" in sig.parameters
    assert sig.parameters["y"].default == 10
    
    # 6. Verify execution delegation
    # Calling the generated function should call engine.execute_tool
    result = generated_func(x=5, y=20)
    assert "Executed add_numbers" in result
    assert "{'x': 5, 'y': 20}" in result  # simplified arg check
