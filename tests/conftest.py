import pytest
import os
import yaml
import json

@pytest.fixture
def temp_config_file(tmp_path):
    """Creates a temporary config.yaml"""
    config_data = {
        "database_path": "data/test.db",
        "log_level": "DEBUG"
    }
    config_file = tmp_path / "brimley_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file

@pytest.fixture
def temp_tools_dir(tmp_path):
    """Creates a temporary tools directory with one valid tool."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    
    tool_def = {
        "tool_name": "test_tool",
        "description": "A test tool",
        "implementation": {"sql_template": []} 
    }
    
    with open(tools_dir / "test_tool.json", "w") as f:
        json.dump(tool_def, f)
        
    return tools_dir
