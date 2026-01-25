import pytest
from brimley.config import load_config, load_tools_from_directory
import os

def test_load_valid_config(temp_config_file):
    """Ensure valid YAML loads into a Python dict."""
    config = load_config(str(temp_config_file))
    assert config["database_path"] == "data/test.db"
    assert config["log_level"] == "DEBUG"

def test_missing_file_error():
    """Ensure graceful failure if config is missing."""
    with pytest.raises(FileNotFoundError):
        load_config("non_existent_file.yaml")

def test_load_tools_directory(temp_tools_dir):
    """Ensure it iterates a folder and loads multiple .json files."""
    tools = load_tools_from_directory(str(temp_tools_dir))
    assert "test_tool" in tools
    assert tools["test_tool"]["tool_name"] == "test_tool"

def test_load_tools_directory_ignores_non_json(temp_tools_dir):
    """Ensure it ignores non-json files."""
    (temp_tools_dir / "readme.txt").write_text("ignore me")
    tools = load_tools_from_directory(str(temp_tools_dir))
    assert len(tools) == 1 
