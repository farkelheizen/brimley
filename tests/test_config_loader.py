import os
import yaml
import pytest
from pathlib import Path
from brimley.config.loader import load_config

def test_load_config_no_file(tmp_path):
    # Should return a default dict if no file exists
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config == {}

def test_load_config_basic(tmp_path):
    config_file = tmp_path / "brimley.yaml"
    content = """
brimley:
  root_dir: "./tools"
config:
  api_key: "secret"
state:
  initial_count: 0
"""
    config_file.write_text(content)
    
    config = load_config(config_file)
    assert config["brimley"]["root_dir"] == "./tools"
    assert config["config"]["api_key"] == "secret"
    assert config["state"]["initial_count"] == 0

def test_load_config_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIMLEY_ENV", "production")
    monkeypatch.setenv("DB_URL", "postgres://localhost")
    
    config_file = tmp_path / "brimley.yaml"
    content = """
brimley:
  env: "${BRIMLEY_ENV}"
config:
  db: "${DB_URL}"
  path: "${HOME_DIR:/tmp}"
  missing: "${MISSING_VAR}"
"""
    config_file.write_text(content)
    
    config = load_config(config_file)
    assert config["brimley"]["env"] == "production"
    assert config["config"]["db"] == "postgres://localhost"
    assert config["config"]["path"] == "/tmp"
    assert config["config"]["missing"] == "" # Or should it stay as is? Usually empty string or default. 
    # Plan says replace ${VAR} and ${VAR:default}. If missing and no default, empty string is common.

def test_load_config_invalid_keys(tmp_path):
    config_file = tmp_path / "brimley.yaml"
    content = """
unknown_key: true
brimley:
  root_dir: "."
"""
    config_file.write_text(content)
    
    # Depending on how strict we want to be. The plan says "Validate structure (keys: ...)"
    # I'll assume it should either filter them or maybe warn. 
    # Let's see if it filters them.
    config = load_config(config_file)
    assert "unknown_key" not in config
    assert "brimley" in config

def test_load_config_includes_mcp_section(tmp_path):
    config_file = tmp_path / "brimley.yaml"
    content = """
mcp:
  embedded: false
  transport: stdio
  host: 0.0.0.0
  port: 9000
"""
    config_file.write_text(content)

    config = load_config(config_file)
    assert "mcp" in config
    assert config["mcp"]["embedded"] is False
    assert config["mcp"]["transport"] == "stdio"
    assert config["mcp"]["host"] == "0.0.0.0"
    assert config["mcp"]["port"] == 9000

def test_load_config_includes_auto_reload_section(tmp_path):
    config_file = tmp_path / "brimley.yaml"
    content = """
auto_reload:
  enabled: true
  interval_ms: 1200
  debounce_ms: 400
  include_patterns: ["*.py", "*.sql"]
  exclude_patterns: [".venv/*"]
"""
    config_file.write_text(content)

    config = load_config(config_file)
    assert "auto_reload" in config
    assert config["auto_reload"]["enabled"] is True
    assert config["auto_reload"]["interval_ms"] == 1200
    assert config["auto_reload"]["debounce_ms"] == 400
    assert config["auto_reload"]["include_patterns"] == ["*.py", "*.sql"]
    assert config["auto_reload"]["exclude_patterns"] == [".venv/*"]
