import pytest
import sys
from pathlib import Path

# Ensure src/ is in the python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

@pytest.fixture
def root_dir(tmp_path):
    """
    Returns a temporary directory to act as the ROOT_DIR for tests.
    Useful for creating temporary function files during discovery tests.
    """
    return tmp_path