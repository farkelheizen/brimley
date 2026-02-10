import pytest
from pathlib import Path
from brimley.discovery.scanner import Scanner
from brimley.core.context import BrimleyContext

def test_entity_discovery_and_registration(tmp_path):
    """
    Test that entities are correctly discovered by the scanner and registered in the context.
    """
    # 1. Setup a mock project with an entity
    entity_dir = tmp_path / "models"
    entity_dir.mkdir()
    
    entity_file = entity_dir / "user_profile.yaml"
    entity_file.write_text("""
type: entity
name: UserProfile
description: "A simple user profile entity."
fields:
  username:
    type: string
  email:
    type: string
""")

    # 2. Run Scanner
    scanner = Scanner(tmp_path)
    scan_result = scanner.scan()
    
    # 3. Assert Discovery
    assert len(scan_result.entities) == 1
    entity = scan_result.entities[0]
    assert entity.name == "UserProfile"
    
    # 4. Test Registration in Context
    ctx = BrimleyContext()
    ctx.entities.register_all(scan_result.entities)
    
    assert "UserProfile" in ctx.entities
    reg_entity = ctx.entities.get("UserProfile")
    assert reg_entity.name == "UserProfile"
    assert reg_entity.raw_definition["description"] == "A simple user profile entity."

def test_entity_invalid_name(tmp_path):
    """Test that entities with invalid names are caught by diagnostics."""
    entity_file = tmp_path / "bad_entity.yaml"
    entity_file.write_text("""
type: entity
name: "Invalid Name With Spaces"
""")
    
    scanner = Scanner(tmp_path)
    scan_result = scanner.scan()
    
    assert len(scan_result.entities) == 0
    assert any(d.error_code == "ERR_INVALID_NAME" for d in scan_result.diagnostics)

def test_entity_duplicate_name(tmp_path):
    """Test that duplicate entity names produce a diagnostic."""
    (tmp_path / "e1.yaml").write_text("type: entity\nname: User")
    (tmp_path / "e2.yaml").write_text("type: entity\nname: User")
    
    scanner = Scanner(tmp_path)
    scan_result = scanner.scan()
    
    assert len(scan_result.entities) == 1
    assert any(d.error_code == "ERR_DUPLICATE_NAME" for d in scan_result.diagnostics)
