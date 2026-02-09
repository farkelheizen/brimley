import pytest
from pathlib import Path
from brimley.discovery.scanner import Scanner
from brimley.core.entity import Entity
from brimley.core.models import SqlFunction, TemplateFunction

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def scanner_test_dir(tmp_path):
    """Create a temporary directory structure for scanner tests."""
    funcs = tmp_path / "functions"
    funcs.mkdir()
    
    # 1. Valid SQL Function
    (funcs / "users.sql").write_text("""/*
---
name: get_users
type: sql_function
return_shape: void
---
*/
SELECT 1;
""")

    # 2. Valid Template Function
    (funcs / "greet.md").write_text("""---
name: greet
type: template_function
return_shape: string
---
Hello
""")
    
    # 3. Ignored File (No header)
    (funcs / "notes.txt").write_text("Just some notes")
    
    # 4. Ignored File (Python without marker in header)
    (funcs / "script.py").write_text("print('hello')")
    
    return funcs

# -----------------------------------------------------------------------------
# Scanner Tests
# -----------------------------------------------------------------------------

def test_scan_identifies_valid_functions(scanner_test_dir):
    scanner = Scanner(root_dir=scanner_test_dir)
    result = scanner.scan()
    
    # Should find get_users and greet
    names = {f.name for f in result.functions}
    assert "get_users" in names
    assert "greet" in names
    assert "notes" not in names
    assert len(result.functions) == 2
    assert len(result.diagnostics) == 0

def test_scan_captures_errors(tmp_path):
    # Setup bad file
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    
    # Invalid Name
    (bad_dir / "123bad.sql").write_text("""/*
---
name: 123bad
type: sql_function
return_shape: void
---
*/
""")
    
    scanner = Scanner(root_dir=bad_dir)
    result = scanner.scan()
    
    assert len(result.functions) == 0
    assert len(result.diagnostics) > 0
    diag = result.diagnostics[0]
    assert diag.error_code == "ERR_INVALID_NAME"
    assert "123bad" in diag.message

def test_scan_detects_duplicates(tmp_path):
    dup_dir = tmp_path / "dups"
    dup_dir.mkdir()
    
    # File 1
    (dup_dir / "a.sql").write_text("""/*
---
name: same_name
type: sql_function
return_shape: void
---
*/""")
    
    # File 2
    (dup_dir / "b.md").write_text("""---
name: same_name
type: template_function
return_shape: string
---""")
    
    scanner = Scanner(root_dir=dup_dir)
    result = scanner.scan()
    
    # One should succeed, one should fail
    assert len(result.functions) == 1
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].error_code == "ERR_DUPLICATE_NAME"

def test_scan_ignores_non_function_files(tmp_path):
    """Ensure files without the magic string in first 500 chars are ignored."""
    d = tmp_path / "ignore"
    d.mkdir()
    (d / "random.md").write_text("# Just a doc\nNo type definition here.")
    
    scanner = Scanner(root_dir=d)
    result = scanner.scan()
    assert len(result.functions) == 0
    assert len(result.diagnostics) == 0
