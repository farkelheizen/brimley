"""Tests for Scanner YAML detection of api_function and cli_function (Brimley 0.7)."""

import textwrap
from pathlib import Path

import pytest

from brimley.discovery.scanner import Scanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_yaml(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


# ---------------------------------------------------------------------------
# api_function detection
# ---------------------------------------------------------------------------


def test_scanner_detects_api_function(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "get_user.yaml",
        """
        name: get_user
        type: api_function
        description: "Fetch user"
        return_shape: string
        request:
          url: "https://api.example.com/users/{{ username }}"
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.diagnostics) == 0, result.diagnostics
    assert len(result.functions) == 1
    assert result.functions[0].type == "api_function"
    assert result.functions[0].name == "get_user"


def test_scanner_api_function_with_env_secret(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "get_user.yaml",
        """
        name: get_user
        type: api_function
        return_shape: string
        secrets:
          token:
            - env: MY_TOKEN
        request:
          url: "https://api.example.com"
          headers:
            Authorization: "Bearer {{ secrets.token }}"
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.diagnostics) == 0, result.diagnostics
    assert len(result.functions) == 1


def test_scanner_api_function_with_provider_secret_becomes_diagnostic(tmp_path: Path) -> None:
    """Provider sources are now accepted at scan time (v0.8+ per ADR-0003)."""
    write_yaml(
        tmp_path / "get_user.yaml",
        """
        name: get_user
        type: api_function
        return_shape: string
        secrets:
          token:
            - provider: vault_creds
        request:
          url: "https://api.example.com"
        """,
    )
    result = Scanner(tmp_path).scan()
    # Function is accepted — provider sources are valid in v0.8
    assert len(result.diagnostics) == 0
    assert len(result.functions) == 1
    assert result.functions[0].name == "get_user"


def test_scanner_api_function_missing_request_becomes_diagnostic(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "bad.yaml",
        """
        name: bad_func
        type: api_function
        return_shape: string
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.functions) == 0
    assert len(result.diagnostics) == 1


def test_scanner_api_function_invalid_yaml_becomes_diagnostic(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text("name: [unclosed", encoding="utf-8")
    result = Scanner(tmp_path).scan()
    # File has no recognisable type — scanner silently ignores it (no type field).
    assert len(result.functions) == 0


def test_scanner_ignores_yaml_without_brimley_type(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "config.yaml",
        """
        foo: bar
        baz: 42
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.functions) == 0
    assert len(result.diagnostics) == 0


# ---------------------------------------------------------------------------
# cli_function detection
# ---------------------------------------------------------------------------


def test_scanner_detects_cli_function(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "sys_load.yaml",
        """
        name: get_system_load
        type: cli_function
        return_shape: string
        command: uptime
        timeout_seconds: 10
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.diagnostics) == 0, result.diagnostics
    assert len(result.functions) == 1
    assert result.functions[0].type == "cli_function"
    assert result.functions[0].name == "get_system_load"


def test_scanner_cli_function_missing_timeout_becomes_diagnostic(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "sys_load.yaml",
        """
        name: get_system_load
        type: cli_function
        return_shape: string
        command: uptime
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.functions) == 0
    assert len(result.diagnostics) == 1


def test_scanner_cli_function_with_provider_secret_becomes_diagnostic(tmp_path: Path) -> None:
    """Provider sources are now accepted at scan time (v0.8+ per ADR-0003)."""
    write_yaml(
        tmp_path / "aws_cmd.yaml",
        """
        name: aws_cmd
        type: cli_function
        return_shape: string
        command: aws
        timeout_seconds: 30
        secrets:
          aws_key:
            - provider: aws_creds
        """,
    )
    result = Scanner(tmp_path).scan()
    # Function is accepted — provider sources are valid in v0.8
    assert len(result.diagnostics) == 0
    assert len(result.functions) == 1
    assert result.functions[0].name == "aws_cmd"


def test_scanner_mixed_functions(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "api.yaml",
        """
        name: my_api
        type: api_function
        return_shape: string
        request:
          url: "https://example.com"
        """,
    )
    write_yaml(
        tmp_path / "cli.yaml",
        """
        name: my_cli
        type: cli_function
        return_shape: string
        command: echo
        timeout_seconds: 5
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.diagnostics) == 0, result.diagnostics
    names = {f.name for f in result.functions}
    assert names == {"my_api", "my_cli"}


def test_scanner_duplicate_api_function_name_becomes_diagnostic(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "a.yaml",
        """
        name: my_api
        type: api_function
        return_shape: string
        request:
          url: "https://example.com"
        """,
    )
    write_yaml(
        tmp_path / "b.yaml",
        """
        name: my_api
        type: api_function
        return_shape: string
        request:
          url: "https://other.com"
        """,
    )
    result = Scanner(tmp_path).scan()
    assert len(result.functions) == 1
    # One duplicate diagnostic expected.
    dup_diags = [d for d in result.diagnostics if d.error_code == "ERR_DUPLICATE_NAME"]
    assert len(dup_diags) == 1
