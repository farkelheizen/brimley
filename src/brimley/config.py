import yaml
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads the global configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A dictionary containing the configuration.
    
    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def load_tools_from_directory(tools_dir: str) -> Dict[str, Any]:
    """
    Iterates through a directory and loads all JSON tool definitions.
    
    Args:
        tools_dir: Directory containing tool definition files.

    Returns:
        A dictionary mapping tool_name to the tool definition dict.
        Non-JSON files are ignored.
    """
    tools = {}
    directory = Path(tools_dir)
    
    if not directory.exists():
        raise FileNotFoundError(f"Tools directory not found: {tools_dir}")

    # Process JSON files
    for file_path in directory.glob("*.json"):
        try:
            with open(file_path, "r") as f:
                tool_def = json.load(f)
                if "tool_name" in tool_def:
                    tools[tool_def["tool_name"]] = tool_def
        except json.JSONDecodeError as e:
            logging.getLogger(__name__).warning(f"Skipping invalid JSON file {file_path}: {e}")
            continue

    # Process YAML files
    for file_path in list(directory.glob("*.yaml")) + list(directory.glob("*.yml")):
        try:
            with open(file_path, "r") as f:
                tool_def = yaml.safe_load(f)
                if tool_def and "tool_name" in tool_def:
                    tools[tool_def["tool_name"]] = tool_def
        except yaml.YAMLError as e:
            logging.getLogger(__name__).warning(f"Skipping invalid YAML file {file_path}: {e}")
            continue
            
    return tools
