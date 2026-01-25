import pytest
import sqlite3
import json
from brimley.core import BrimleyEngine
from brimley.backend.sqlite import SQLiteConnection
from pydantic import ValidationError

@pytest.fixture
def e2e_setup(tmp_path):
    """Sets up a temp tools dir and a temp db."""
    # 1. Setup Tools
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    
    get_customer_tool = {
        "tool_name": "get_customer_e2e",
        "tool_type": "LOCAL_SQL",
        "description": "Get customer by ID",
        "implementation": {
            "sql_template": ["SELECT * FROM customers WHERE id = :id"]
        },
        "return_shape": {"type": "RECORD"},
        "arguments": {
            "inline": [
                {"name": "id", "type": "int", "required": True}
            ]
        }
    }
    
    with open(tools_dir / "get_customer.json", "w") as f:
        json.dump(get_customer_tool, f)

    # 2. Setup DB
    db_path = tmp_path / "data.db"
    with SQLiteConnection(str(db_path)) as conn:
        conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO customers (id, name) VALUES (1, 'Brimley User')")
        conn.commit()

    return tools_dir, db_path

def test_e2e_execution(e2e_setup):
    """
    1. Initialize Engine.
    2. Call execute_tool.
    3. Assert result from DB.
    """
    tools_dir, db_path = e2e_setup
    
    engine = BrimleyEngine(
        tools_dir=str(tools_dir),
        db_path=str(db_path)
    )
    
    result = engine.execute_tool("get_customer_e2e", {"id": 1})
    
    assert isinstance(result, dict)
    assert result["name"] == "Brimley User"

def test_e2e_validation_error(e2e_setup):
    """Call with bad args, ensure Engine raises error."""
    tools_dir, db_path = e2e_setup
    
    engine = BrimleyEngine(
        tools_dir=str(tools_dir),
        db_path=str(db_path)
    )
    
    # Missing 'id'
    with pytest.raises(ValidationError):
        engine.execute_tool("get_customer_e2e", {"wrong_arg": 1})
        
def test_e2e_tool_not_found(e2e_setup):
    """Call non-existent tool."""
    tools_dir, db_path = e2e_setup
    engine = BrimleyEngine(str(tools_dir), str(db_path))
    
    with pytest.raises(KeyError, match="Tool 'missing_tool' not found"):
        engine.execute_tool("missing_tool", {})
