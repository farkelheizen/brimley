import pytest
from sqlalchemy import create_engine, text
from brimley.execution.sql_runner import SqlRunner
from brimley.core.models import SqlFunction
from brimley.core.context import BrimleyContext

@pytest.fixture
def engine():
    # In-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"))
        conn.execute(text("INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')"))
        conn.execute(text("INSERT INTO users (id, name, email) VALUES (2, 'Bob', 'bob@example.com')"))
        conn.commit()
    return engine

@pytest.fixture
def runner():
    return SqlRunner()

@pytest.fixture
def context(engine):
    ctx = BrimleyContext()
    ctx.app["user_id"] = 1
    ctx.databases = {"default": engine}
    return ctx

def test_sql_execution_select(runner, context):
    func = SqlFunction(
        name="get_user",
        type="sql_function",
        return_shape="dict[]",
        sql_body="SELECT id, name FROM users WHERE id = :id",
        arguments={
            "inline": {
                "id": "int"
            }
        }
    )
    
    # Run with explicit argument
    result = runner.run(func, {"id": 1}, context)
    
    assert len(result) == 1
    assert result[0]["name"] == "Alice"
    assert result[0]["id"] == 1

def test_sql_execution_context_injection(runner, context):
    func = SqlFunction(
        name="get_my_profile",
        type="sql_function",
        return_shape="dict[]",
        sql_body="SELECT * FROM users WHERE id = :uid",
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
    
    assert len(result) == 1
    assert result[0]["name"] == "Alice"

def test_sql_execution_insert(runner, context):
    func = SqlFunction(
        name="add_user",
        type="sql_function",
        return_shape="dict",
        sql_body="INSERT INTO users (id, name, email) VALUES (:id, :name, :email)",
        arguments={
            "inline": {
                "id": "int",
                "name": "string",
                "email": "string"
            }
        }
    )
    
    result = runner.run(func, {"id": 3, "name": "Charlie", "email": "charlie@example.com"}, context)
    
    assert result["rows_affected"] == 1
    
    # Verify insertion
    engine = context.databases["default"]
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM users WHERE id = 3")).mappings().one()
        assert res["name"] == "Charlie"

def test_sql_execution_missing_connection(runner):
    context = BrimleyContext()
    # No databases registered
    
    func = SqlFunction(
        name="fail_test",
        type="sql_function",
        sql_body="SELECT 1",
        connection="missing",
        return_shape="void"
    )
    
    with pytest.raises(RuntimeError, match="Database connection 'missing' not found"):
        runner.run(func, {}, context)
