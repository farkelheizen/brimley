import re
import yaml
from typing import Dict, Tuple, Any

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Extracts YAML frontmatter and body from content.
    Supports Standard (---) and SQL comment style (/* --- ... --- */).
    
    Returns:
        (metadata_dict, body_string)
    
    Raises:
        ValueError: If YAML is malformed.
    """
    content = content.strip()
    
    # 1. SQL Style: Starts with /*
    # We look for /* \n --- ... --- \n */
    # Using regex to find the block
    sql_match = re.match(r'^\/\*\s*\n(---[\s\S]*?---)\s*\n\*\/', content)
    
    if sql_match:
        yaml_block = sql_match.group(1)
        # Body is everything after the match end
        body = content[sql_match.end():].strip()
        
        # Remove the dashes for parsing
        yaml_text = yaml_block.strip('-').strip()
        try:
            meta = yaml.safe_load(yaml_text) or {}
            return meta, body
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in frontmatter: {e}")

    # 2. Standard Markdown/YAML Style: Starts with ---
    if content.startswith("---"):
        # split by ---. Limit 2 splits: empty, yaml, body
        parts = re.split(r'^---$', content, maxsplit=2, flags=re.MULTILINE)
        
        if len(parts) >= 3:
            # parts[0] is empty (before first ---)
            # parts[1] is yaml
            # parts[2] is body
            yaml_text = parts[1].strip()
            body = parts[2].strip()
            
            try:
                meta = yaml.safe_load(yaml_text) or {}
                return meta, body
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in frontmatter: {e}")
            
    # No frontmatter found
    return {}, content
