import pytest
import sqlite3
from brimley.backend.runner import run_local_sql
from brimley.backend.sqlite import SQLiteConnection
from brimley.schemas import ToolDefinition, ToolType, Implementation, ReturnShape, ReturnType, ArgumentsBlock

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")

@pytest.fixture
def insert_tool():
    return ToolDefinition(
        tool_name="insert_user",
        tool_type=ToolType.LOCAL_SQL,
        description="Inserts a user",
        implementation=Implementation(sql_template=["INSERT INTO users (name, age) VALUES (:name, :age)"]),
        return_shape=ReturnShape(type=ReturnType.VOID),
        arguments=ArgumentsBlock(inline=[])
    )

def test_run_local_sql_execution(db_path, insert_tool):
    """Test that SQL is actually executed against the DB."""
    # Setup DB
    with SQLiteConnection(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        conn.commit()
    
    # Run Tool
    args = {"name": "Alice", "age": 30}
    
    # We haven't implemented return shape logic yet (P3.S3), so for P3.S2 we might just expect it not to crash
    # and to have performed the side effect.
    run_local_sql(insert_tool, args, db_path)
    
    # Verify DB
    with SQLiteConnection(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE name = 'Alice'").fetchone()
        assert row is not None
        assert row["name"] == "Alice"
        assert row["age"] == 30
