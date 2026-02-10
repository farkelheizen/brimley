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
