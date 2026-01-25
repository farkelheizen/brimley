import pytest
import sqlite3
from brimley.backend.sqlite import SQLiteConnection

def test_sqlite_connection_context_manager(tmp_path):
    """Ensure context manager opens and closes connection."""
    db_path = tmp_path / "test.db"
    
    # Test context manager usage
    with SQLiteConnection(str(db_path)) as conn:
        assert isinstance(conn, sqlite3.Connection)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INT, name TEXT)")
        cursor.execute("INSERT INTO test VALUES (1, 'Brimley')")
        conn.commit()
        
    # Verify file exists
    assert db_path.exists()

def test_sqlite_row_factory(tmp_path):
    """Ensure row_factory is set to sqlite3.Row for dict-like access."""
    db_path = tmp_path / "test.db"
    
    with SQLiteConnection(str(db_path)) as conn:
        conn.execute("CREATE TABLE test (id INT, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'Brimley')")
        
        row = conn.execute("SELECT * FROM test").fetchone()
        
        # Access by name (dict-like)
        assert row["name"] == "Brimley"
        assert row["id"] == 1
        # Access by index (tuple-like)
        assert row[1] == "Brimley"
