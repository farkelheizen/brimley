import pytest
from brimley.discovery.scanner import Scanner
from brimley.core.context import BrimleyContext
from brimley.core.models import DiscoveredEntity

def test_entity_discovery_and_registration(tmp_path):
    """
    Test that entities are correctly discovered by the scanner and registered in the context.
    """
    # 1. Setup a mock project with an entity
    entity_dir = tmp_path / "models"
    entity_dir.mkdir()
    
    entity_file = entity_dir / "user_profile.py"
    entity_file.write_text("""
from brimley import entity

@entity(name="UserProfile", description="A simple user profile entity.")
class UserProfile:
    pass
""")

    # 2. Run Scanner
    scanner = Scanner(tmp_path)
    scan_result = scanner.scan()
    
    # 3. Assert Discovery
    assert len(scan_result.entities) == 1
    entity = scan_result.entities[0]
    assert isinstance(entity, DiscoveredEntity)
    assert entity.name == "UserProfile"
    assert entity.type == "python_entity"
    
    # 4. Test Registration in Context
    ctx = BrimleyContext()
    ctx.entities.register_all(scan_result.entities)
    
    assert "UserProfile" in ctx.entities
    reg_entity = ctx.entities.get("UserProfile")
    assert reg_entity.name == "UserProfile"
    assert reg_entity.handler is not None

def test_entity_invalid_name(tmp_path):
    """Test that entities with invalid names are caught by diagnostics."""
    entity_file = tmp_path / "bad_entity.py"
    entity_file.write_text("""
from brimley import entity

@entity(name="Invalid Name With Spaces")
class BadEntity:
    pass
""")
    
    scanner = Scanner(tmp_path)
    scan_result = scanner.scan()
    
    assert len(scan_result.entities) == 0
    assert any(d.error_code == "ERR_INVALID_NAME" for d in scan_result.diagnostics)

def test_entity_duplicate_name(tmp_path):
    """Test that duplicate entity names produce a diagnostic."""
    (tmp_path / "e1.py").write_text(
        "from brimley import entity\n\n@entity(name=\"User\")\nclass UserOne:\n    pass\n"
    )
    (tmp_path / "e2.py").write_text(
        "from brimley import entity\n\n@entity(name=\"User\")\nclass UserTwo:\n    pass\n"
    )
    
    scanner = Scanner(tmp_path)
    scan_result = scanner.scan()
    
    assert len(scan_result.entities) == 1
    assert any(d.error_code == "ERR_DUPLICATE_NAME" for d in scan_result.diagnostics)
