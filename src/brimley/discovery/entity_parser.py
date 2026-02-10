from pathlib import Path
import yaml
from typing import Dict, Any, Optional
from brimley.core.entity import Entity

class UserDefinedEntity(Entity):
    """
    A placeholder for a user-defined entity discovered on disk.
    In Phase 1, this stores the raw definition.
    """
    name: str # Required for registry
    raw_definition: Dict[str, Any]

def parse_entity_file(file_path: Path) -> UserDefinedEntity:
    """
    Parses a .yaml file to extract an Entity definition.
    
    Raises:
        ValueError: If file is not a valid entity or has missing name.
        FileNotFoundError: If file does not exist.
    """
    try:
        content = file_path.read_text()
        data = yaml.safe_load(content)
    except Exception as e:
        raise ValueError(f"Failed to read or parse YAML in {file_path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Entity file {file_path} must be a YAML object.")

    if data.get("type") != "entity":
        raise ValueError(f"File {file_path} is not an entity (missing type: entity).")

    name = data.get("name")
    if not name:
        raise ValueError(f"Entity file {file_path} is missing 'name' field.")

    return UserDefinedEntity(name=name, raw_definition=data)
