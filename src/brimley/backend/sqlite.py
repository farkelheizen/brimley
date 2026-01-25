import sqlite3
from pathlib import Path
from typing import Optional
from brimley.extensions import get_registry

class SQLiteConnection:
    """
    Context manager for SQLite database connections.
    Ensures connections are properly opened, configured with strict typing rows,
    and closed. Automatically registers UDFs from registry.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        # Ensure directory exists if it's a file path
        if self.db_path != ":memory:":
            path = Path(self.db_path)
            path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            self.db_path,
            # detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES # Optional depending on needs
        )
        
        # Enable accessing columns by name (dict-like)
        self.conn.row_factory = sqlite3.Row
        
        # Enable foreign keys by default for safety
        self.conn.execute("PRAGMA foreign_keys = ON;")
        
        # Register UDFs
        for name, udf in get_registry().items():
            try:
                self.conn.create_function(udf.name, udf.num_args, udf.func)
            except Exception as e:
                # Log warning?
                # print(f"Failed to register UDF {name}: {e}")
                pass

        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            # We don't auto-commit here; implementation logic should handle transactions.
            # But the 'with' block of the *Connection object* (not this wrapper) usually doesn't auto-commit unless using the transaction pattern.
            # For this simple wrapper, we just close.
            self.conn.close()
