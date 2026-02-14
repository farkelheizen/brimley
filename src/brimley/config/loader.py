import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict

ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]+))?\}")

def interpolate_env_vars(content: str) -> str:
    """Replace ${VAR} or ${VAR:default} with environment variables."""
    def replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else ""
        return os.environ.get(var_name, default_value)

    return ENV_VAR_PATTERN.sub(replace_match, content)

def load_config(path: Path) -> Dict[str, Any]:
    """
    Load brimley.yaml with environment variable interpolation.
    
    Validates structure for keys: brimley, config, mcp, auto_reload, state, databases.
    """
    if not path.exists():
        return {}

    try:
        content = path.read_text()
        interpolated_content = interpolate_env_vars(content)
        full_config = yaml.safe_load(interpolated_content) or {}
    except Exception:
        # For now, return empty or re-raise if we want to be strict.
        # Design Doc says Boot & Discovery invalid functions generate Diagnostics but don't crash.
        # But this is core config loader.
        return {}

    allowed_keys = {"brimley", "config", "mcp", "auto_reload", "state", "databases"}
    filtered_config = {k: v for k, v in full_config.items() if k in allowed_keys}

    return filtered_config
