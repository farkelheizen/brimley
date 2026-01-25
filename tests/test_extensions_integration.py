import pytest
from brimley.extensions import register_sqlite_function, clear_registry
from brimley.backend.sqlite import SQLiteConnection

@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield

def test_sqlite_udf_execution():
    """Ensure registered UDFs are callable in SQL."""
    
    # 1. Register UDF
    @register_sqlite_function(name="py_double", num_args=1)
    def py_double(x):
        return x * 2
        
    # 2. Use Connection
    with SQLiteConnection(":memory:") as conn:
        # 3. Call in SQL
        val = conn.execute("SELECT py_double(10)").fetchone()[0]
        assert val == 20
