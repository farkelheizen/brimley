"""Tests for ApiFunction and CliFunction models (Brimley 0.7)."""

import pytest
from pydantic import ValidationError

from brimley.core.models import (
    ApiFunction,
    ApiRequestConfig,
    CliFunction,
    CliParsingConfig,
    SecretSource,
)


# ---------------------------------------------------------------------------
# ApiRequestConfig
# ---------------------------------------------------------------------------


def test_api_request_config_minimal() -> None:
    req = ApiRequestConfig(url="https://example.com")
    assert req.method == "GET"
    assert req.timeout == 30.0
    assert req.headers is None


def test_api_request_config_full() -> None:
    req = ApiRequestConfig(
        method="POST",
        url="https://api.example.com/data",
        headers={"Authorization": "Bearer {{ token }}"},
        timeout=10.0,
        body={"key": "value"},
    )
    assert req.method == "POST"
    assert req.timeout == 10.0


def test_api_request_config_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ApiRequestConfig(url="https://example.com", timeout=-1.0)


# ---------------------------------------------------------------------------
# ApiFunction
# ---------------------------------------------------------------------------


def test_api_function_minimal() -> None:
    func = ApiFunction(
        name="get_user",
        type="api_function",
        return_shape="string",
        request={"url": "https://example.com"},
    )
    assert func.type == "api_function"
    assert func.name == "get_user"
    assert func.secrets is None
    assert func.response is None


def test_api_function_with_secrets() -> None:
    func = ApiFunction(
        name="get_user",
        type="api_function",
        return_shape="string",
        request={"url": "https://example.com"},
        secrets={"token": [{"env": "MY_TOKEN"}]},
    )
    assert func.secrets is not None
    assert func.secrets["token"][0].env == "MY_TOKEN"


def test_api_function_with_response_map() -> None:
    func = ApiFunction(
        name="get_user",
        type="api_function",
        return_shape="string",
        request={"url": "https://example.com"},
        response={200: {"type": "json"}, 404: {"error": "Not found"}},
    )
    assert 200 in func.response
    assert func.response[404]["error"] == "Not found"


def test_api_function_missing_request_raises() -> None:
    with pytest.raises(ValidationError):
        ApiFunction(
            name="get_user",
            type="api_function",
            return_shape="string",
        )


def test_api_function_missing_return_shape_raises() -> None:
    with pytest.raises(ValidationError):
        ApiFunction(
            name="get_user",
            type="api_function",
            request={"url": "https://example.com"},
        )


# ---------------------------------------------------------------------------
# CliParsingConfig
# ---------------------------------------------------------------------------


def test_cli_parsing_config_defaults() -> None:
    cfg = CliParsingConfig()
    assert cfg.strategy == "text"
    assert cfg.pattern is None


def test_cli_parsing_config_regex() -> None:
    cfg = CliParsingConfig(strategy="regex", pattern=r"load: (?P<val>\d+\.\d+)", capture_group="val")
    assert cfg.strategy == "regex"
    assert cfg.capture_group == "val"


def test_cli_parsing_config_json() -> None:
    cfg = CliParsingConfig(strategy="json")
    assert cfg.strategy == "json"


def test_cli_parsing_config_invalid_strategy_raises() -> None:
    with pytest.raises(ValidationError):
        CliParsingConfig(strategy="xml")


# ---------------------------------------------------------------------------
# CliFunction
# ---------------------------------------------------------------------------


def test_cli_function_minimal() -> None:
    func = CliFunction(
        name="run_cmd",
        type="cli_function",
        return_shape="string",
        command="echo",
        timeout_seconds=10.0,
    )
    assert func.type == "cli_function"
    assert func.command == "echo"
    assert func.args == []
    assert func.cwd is None
    assert func.env is None
    assert func.secrets is None
    assert func.parsing is None


def test_cli_function_missing_timeout_raises() -> None:
    with pytest.raises(ValidationError):
        CliFunction(
            name="run_cmd",
            type="cli_function",
            return_shape="string",
            command="echo",
        )


def test_cli_function_negative_timeout_raises() -> None:
    with pytest.raises(ValidationError):
        CliFunction(
            name="run_cmd",
            type="cli_function",
            return_shape="string",
            command="echo",
            timeout_seconds=-5.0,
        )


def test_cli_function_with_args_and_env() -> None:
    func = CliFunction(
        name="run_cmd",
        type="cli_function",
        return_shape="string",
        command="ls",
        args=["-la", "/tmp"],
        timeout_seconds=5.0,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert func.args == ["-la", "/tmp"]
    assert func.env == {"PATH": "/usr/bin:/bin"}


def test_cli_function_with_parsing() -> None:
    func = CliFunction(
        name="run_cmd",
        type="cli_function",
        return_shape="string",
        command="uptime",
        timeout_seconds=10.0,
        parsing={"strategy": "regex", "pattern": r"load average: (\d+\.\d+)"},
    )
    assert func.parsing.strategy == "regex"


def test_cli_function_with_secrets() -> None:
    func = CliFunction(
        name="aws_cmd",
        type="cli_function",
        return_shape="string",
        command="aws",
        timeout_seconds=30.0,
        secrets={"aws_key": [{"env": "AWS_ACCESS_KEY_ID"}]},
    )
    assert func.secrets["aws_key"][0].env == "AWS_ACCESS_KEY_ID"
