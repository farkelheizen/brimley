from pathlib import Path
from pydantic import ValidationError
from brimley.core.models import TemplateFunction
from brimley.discovery.utils import parse_frontmatter

def parse_template_file(file_path: Path) -> TemplateFunction:
    """
    Parses a .md or .yaml file into a TemplateFunction object.
    
    Args:
        file_path: Path to the .md/.yaml file.
        
    Returns:
        TemplateFunction
        
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

    # Inject parsed body
    # If body is present, it's the template
    if body and "template_body" not in meta:
        meta["template_body"] = body
    
    # Ensure type is set if missing, but usually mandatory in YAML
    if "type" not in meta:
        # Heuristic: if .md, assume template_function? 
        # Strict config says explicit type required.
        # But let's set it to help validation if user forgot, 
        # though the model will validate it must be 'template_function'
        meta["type"] = "template_function"

    try:
        return TemplateFunction(**meta)
    except ValidationError as e:
        raise ValueError(f"Validation error in {file_path}: {e}")
