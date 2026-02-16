import pytest
from typing import Annotated
from brimley.execution.python_runner import PythonRunner
from brimley.core.models import PythonFunction
from brimley.core.context import BrimleyContext
from brimley import AppState, Config
# Connection might be mocked or imported if defined
from brimley.core.di import Connection

@pytest.fixture
def runner():
    return PythonRunner()

@pytest.fixture
def context():
    ctx = BrimleyContext()
    ctx.config.app_name = "TestProject"
    ctx.app["start_time"] = 12345.0
    # Mock a database connection
    ctx.databases = {"default": "FakeDBConnection"}
    return ctx

def test_python_simple_args(runner, context):
    """Test calling a python function with simple arguments."""
    def my_handler(name: str, age: int):
        return f"{name} is {age}"

    func = PythonFunction(
        name="simple",
        type="python_function",
        return_shape="string"
    )
    
    # Manually attach the callable for the test runner to find
    # In a real scenario, this would be loaded from a module
    runner._params_cache = {"simple": my_handler} 

    # We bypass the module loading by mocking/injecting the callable into the runner's resolution logic
    # ...
    pass 

# To make testing easier without actual files on disk, 
# I will implement a 'registry override' or 'direct callable' support in PythonRunner for testing.

class MockPythonRunner(PythonRunner):
    def __init__(self, handler_map):
        self.handler_map = handler_map
        
    def _load_handler(self, handler_path: str):
        return self.handler_map.get(handler_path)

def test_python_di_injection(context):
    def di_func(
        name: str, 
        db: Annotated[Connection, "default"],
        start: Annotated[float, AppState("start_time")],
        proj: Annotated[str, Config("app_name")]
    ):
        return {
            "name": name,
            "db_repr": str(db),
            "start": start,
            "proj": proj
        }

    runner = MockPythonRunner({"test.di": di_func})

    func = PythonFunction(
        name="di_test",
        type="python_function",
        return_shape="dict",
        handler="test.di"
    )

    result = runner.run(func, {"name": "Alice"}, context)
    
    assert result["name"] == "Alice"
    assert result["db_repr"] == "FakeDBConnection"
    assert result["start"] == 12345.0
    assert result["proj"] == "TestProject"

def test_python_missing_di(context):
    """Test what happens when a requested DI resource is missing."""
    def bad_func(val: Annotated[str, Config("missing_key")]):
        return val

    runner = MockPythonRunner({"test.bad": bad_func})
    
    func = PythonFunction(
        name="bad_test",
        type="python_function",
        return_shape="string",
        handler="test.bad"
    )
    
    # Depending on implementation, this might raise an error or pass None
    # Usually strictly typed DI should raise error if missing
    # Config/AppState access might raise KeyError or AttributeError
    with pytest.raises((KeyError, AttributeError)):
        runner.run(func, {}, context)


def test_python_injects_brimley_context_by_type(context):
    def context_func(name: str, ctx: BrimleyContext):
        return {
            "name": name,
            "ctx_id": id(ctx),
        }

    runner = MockPythonRunner({"test.context": context_func})

    func = PythonFunction(
        name="context_test",
        type="python_function",
        return_shape="dict",
        handler="test.context",
    )

    result = runner.run(func, {"name": "Alice"}, context)

    assert result["name"] == "Alice"
    assert result["ctx_id"] == id(context)


def test_python_injects_fastmcp_context_from_runtime_injections(context):
    FastMCPContext = type("Context", (), {"__module__": "mcp.server.fastmcp"})
    runtime_mcp_ctx = FastMCPContext()

    def mcp_func(name: str, mcp_ctx: FastMCPContext):
        return {
            "name": name,
            "mcp_ctx_id": id(mcp_ctx),
        }

    runner = MockPythonRunner({"test.mcp": mcp_func})

    func = PythonFunction(
        name="mcp_test",
        type="python_function",
        return_shape="dict",
        handler="test.mcp",
    )

    result = runner.run(
        func,
        {"name": "Alice"},
        context,
        runtime_injections={"mcp_context": runtime_mcp_ctx},
    )

    assert result["name"] == "Alice"
    assert result["mcp_ctx_id"] == id(runtime_mcp_ctx)


def test_python_missing_fastmcp_runtime_injection_raises_type_error(context):
    FastMCPContext = type("Context", (), {"__module__": "mcp.server.fastmcp"})

    def mcp_func(mcp_ctx: FastMCPContext):
        return id(mcp_ctx)

    runner = MockPythonRunner({"test.mcp_missing": mcp_func})

    func = PythonFunction(
        name="mcp_missing_test",
        type="python_function",
        return_shape="int",
        handler="test.mcp_missing",
    )

    with pytest.raises(TypeError):
        runner.run(func, {}, context)
