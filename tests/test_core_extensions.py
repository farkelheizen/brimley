import pytest
from brimley.core import BrimleyEngine
from brimley.extensions import get_registry, clear_registry

@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield

def test_engine_loads_extensions(tmp_path):
    """Ensure Engine loads the python file which registers the UDF."""
    
    # 1. Create dummy extension file
    ext_file = tmp_path / "extensions.py"
    ext_file.write_text("""
from brimley.extensions import register_sqlite_function

@register_sqlite_function("test_udf", 0)
def test_udf():
    return 100
""")
    
    # 2. Create dummy tools dir (required by engine)
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    
    # 3. Init Engine
    engine = BrimleyEngine(
        tools_dir=str(tools_dir),
        db_path=":memory:",
        extensions_file=str(ext_file)
    )
    
    # 4. Verify Registry
    registry = get_registry()
    assert "test_udf" in registry
