import pytest
from brimley.backend.runner import run_local_sql
from brimley.backend.sqlite import SQLiteConnection
from brimley.schemas import ToolDefinition, ToolType, Implementation, ReturnShape, ReturnType, ArgumentsBlock

@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    with SQLiteConnection(path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT)")
        conn.execute("INSERT INTO users (id, name, role) VALUES (1, 'Alice', 'Admin')")
        conn.execute("INSERT INTO users (id, name, role) VALUES (2, 'Bob', 'User')")
        conn.commit()
    return path

def run_query(sql, return_type, args, db_path):
    tool = ToolDefinition(
        tool_name="test_tool",
        tool_type=ToolType.LOCAL_SQL,
        description="test",
        implementation=Implementation(sql_template=[sql]),
        return_shape=ReturnShape(type=return_type),
        arguments=ArgumentsBlock(inline=[])
    )
    return run_local_sql(tool, args, db_path)

def test_sqlite_select_table(db_path):
    """TABLE should return list of dicts."""
    res = run_query("SELECT name, role FROM users ORDER BY id", ReturnType.TABLE, {}, db_path)
    assert isinstance(res, list)
    assert len(res) == 2
    assert res[0]["name"] == "Alice"
    assert res[1]["role"] == "User"

def test_sqlite_select_record(db_path):
    """RECORD should return single dict."""
    res = run_query("SELECT * FROM users WHERE id = :id", ReturnType.RECORD, {"id": 1}, db_path)
    assert isinstance(res, dict)
    assert res["name"] == "Alice"

def test_sqlite_select_record_none(db_path):
    """RECORD should return None (or raise?) if not found. Let's assume None for now."""
    res = run_query("SELECT * FROM users WHERE id = 999", ReturnType.RECORD, {}, db_path)
    assert res is None

def test_sqlite_select_value(db_path):
    """VALUE should return single scalar."""
    res = run_query("SELECT count(*) FROM users", ReturnType.VALUE, {}, db_path)
    assert res == 2

def test_sqlite_select_list(db_path):
    """LIST should return list of scalars."""
    res = run_query("SELECT name FROM users ORDER BY id", ReturnType.LIST, {}, db_path)
    assert res == ["Alice", "Bob"]

def test_sqlite_update_void(db_path):
    """VOID should return a success message or rows affected? 
    Spec in docs says: 'rows_affected' in return for UPDATE_VOID check?"
    Let's return a dict with metadata, or just None?
    REFERENCE doc says 'No return data (just success/fail)'.
    Let's return None for now, but implementation plan says:
    'verify rows_affected in return'. 
    Let's make VOID return {'rows_affected': N} for convenience?
    """
    res = run_query("UPDATE users SET role='Super' WHERE id=1", ReturnType.VOID, {}, db_path)
    # If the plan says verify rows_affected, let's assume we return a dict for VOID with metadata.
    assert isinstance(res, dict)
    assert res["rows_affected"] == 1

def test_sqlite_update_returning(db_path):
    """UPDATE ... RETURNING should work like RECORD."""
    # SQLite 3.35+ supports RETURNING
    res = run_query(
        "UPDATE users SET role='Super' WHERE id=1 RETURNING name, role", 
        ReturnType.RECORD, 
        {}, 
        db_path
    )
    assert res["name"] == "Alice"
    assert res["role"] == "Super"
