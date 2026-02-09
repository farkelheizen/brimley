from pathlib import Path
from pydantic import ValidationError
from brimley.core.models import SqlFunction
from brimley.discovery.utils import parse_frontmatter

def parse_sql_file(file_path: Path) -> SqlFunction:
    """
    Parses a .sql file into a SqlFunction object.
    
    Args:
        file_path: Path to the .sql file.
        
    Returns:
        SqlFunction
        
    Raises:
        ValueError: If parsing fails or required metadata is missing.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ValueError(f"Could not read file {file_path}: {e}")

    try:
        meta, body = parse_frontmatter(content)
    except ValueError as e:
        raise ValueError(f"Frontmatter parsing error in {file_path}: {e}")

    # Inject parsed body into metadata for model validation
    # SqlFunction requires 'sql_body'
    meta["sql_body"] = body
    
    # Ensure type is set if missing (default logic could go here, but for now trust frontmatter)
    if "type" not in meta:
        meta["type"] = "sql_function"

    try:
        return SqlFunction(**meta)
    except ValidationError as e:
        raise ValueError(f"Validation error in {file_path}: {e}")
