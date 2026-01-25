import pytest
import sqlite3
from brimley.extensions import register_sqlite_function, get_registry, clear_registry
from brimley.backend.sqlite import SQLiteConnection

@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield

def test_register_udf():
    """Ensure decorator adds to registry."""
    @register_sqlite_function(name="py_add", num_args=2)
    def my_add(a, b):
        return a + b
    
    registry = get_registry()
    assert "py_add" in registry
    assert registry["py_add"].name == "py_add"
    assert registry["py_add"].num_args == 2
    assert registry["py_add"].func(1, 2) == 3

# Implementation for P1.S2 will be needed to pass this one, 
# but P1.S1 is just the registry so I'll comment this usage test out 
# or keep it simple to verify registry logic only?
# I'll wait for P1.S2 to test integration with SQLiteConnection.
