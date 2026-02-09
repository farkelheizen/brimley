import pytest
from brimley.execution.sql_runner import SqlRunner
from brimley.core.models import SqlFunction
from brimley.core.context import BrimleyContext

@pytest.fixture
def runner():
    return SqlRunner()

@pytest.fixture
def context():
    ctx = BrimleyContext()
    ctx.app["user_id"] = 999
    ctx.databases = {"default": "sqlite:///:memory:"}
    return ctx

def test_sql_execution_simple(runner, context):
    func = SqlFunction(
        name="get_user",
        type="sql_function",
        return_shape="dict",
        sql_body="SELECT * FROM users WHERE id = :user_id",
        arguments={
            "inline": {
                "user_id": "int"
            }
        }
    )
    
    # Run with explicit argument
    result = runner.run(func, {"user_id": 123}, context)
    
    # Verify mock output structure
    assert result["function"] == "get_user"
    assert result["executed_sql"] == "SELECT * FROM users WHERE id = :user_id"
    assert result["parameters"]["user_id"] == 123
    assert result["connection"] == "default"

def test_sql_execution_context_injection(runner, context):
    func = SqlFunction(
        name="get_my_orders",
        type="sql_function",
        return_shape="list",
        sql_body="SELECT * FROM orders WHERE user_id = :uid",
        arguments={
            "inline": {
                "uid": {
                    "type": "int",
                    "from_context": "app.user_id"
                }
            }
        }
    )
    
    # Run without explicit argument, relying on context injection
    result = runner.run(func, {}, context)
    
    assert result["parameters"]["uid"] == 999

def test_sql_execution_missing_arg(runner, context):
    func = SqlFunction(
        name="fail_test",
        type="sql_function",
        return_shape="void",
        sql_body="SELECT :val",
        arguments={
            "inline": {
                "val": "string"
            }
        }
    )
    
    with pytest.raises(ValueError, match="Missing required argument"):
        runner.run(func, {}, context)
