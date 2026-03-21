"""Security tests for ApiRunner — SSRF, header injection, template injection (Brimley 0.7, B07-S11).

Payloads drawn from PayloadAllTheThings and OWASP SSRF/header-injection categories.
Each attack vector MUST be rejected by the runner before the HTTP request is made.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from brimley.core.context import BrimleyContext
from brimley.core.models import ApiFunction
from brimley.execution.api_runner import (
    ApiRunner,
    _validate_headers,
    _validate_url_scheme,
)
from brimley.utils.diagnostics import BrimleyExecutionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_func(**kwargs: Any) -> ApiFunction:
    defaults = {
        "name": "test_api",
        "type": "api_function",
        "return_shape": "string",
        "request": {"url": "https://example.com/api", "method": "GET"},
    }
    defaults.update(kwargs)
    return ApiFunction(**defaults)


# ---------------------------------------------------------------------------
# URL scheme validation — SSRF mitigation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        # Non-HTTP(S) schemes
        "file:///etc/passwd",
        "ftp://attacker.com/malware",
        "gopher://attacker.com:70/_GET / HTTP/1.0",
        "dict://attacker.com:11111/",
        "ldap://attacker.com/",
        "sftp://attacker.com/",
        "tftp://attacker.com:12346/",
        # Data URIs
        "data:text/plain;base64,SGVsbG8=",
        # Protocol-relative (no scheme)
        "//attacker.com/path",
    ],
)
def test_validate_url_scheme_rejects_non_http_schemes(url: str) -> None:
    with pytest.raises(BrimleyExecutionError, match="(?i)scheme|disallowed"):
        _validate_url_scheme(url, "test_func")


def test_validate_url_scheme_accepts_http() -> None:
    _validate_url_scheme("http://example.com/api", "fn")


def test_validate_url_scheme_accepts_https() -> None:
    _validate_url_scheme("https://api.github.com/users/alice", "fn")


def test_validate_url_scheme_rejects_embedded_credentials() -> None:
    with pytest.raises(BrimleyExecutionError, match="credential"):
        _validate_url_scheme("https://user:pass@example.com/api", "fn")


def test_validate_url_scheme_rejects_embedded_username_only() -> None:
    with pytest.raises(BrimleyExecutionError, match="credential"):
        _validate_url_scheme("https://user@example.com/api", "fn")


# ---------------------------------------------------------------------------
# SSRF via template variable injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "user_provided_url",
    [
        "file:///etc/shadow",
        "ftp://internal.corp/secrets",
        "gopher://127.0.0.1:25/",
        "http://user:pass@example.com/",
    ],
)
def test_api_runner_rejects_ssrf_url_from_template(user_provided_url: str) -> None:
    """SSRF via LLM-controlled template variable injected into URL."""
    func = _make_func(
        request={"url": "{{ target_url }}", "method": "GET"},
    )
    context = BrimleyContext()
    runner = ApiRunner()

    with patch.object(runner, "_async_request", new=AsyncMock(return_value="ok")):
        with pytest.raises(BrimleyExecutionError):
            runner.run(func, {"target_url": user_provided_url}, context)


# ---------------------------------------------------------------------------
# Header injection prevention (CRLF injection / response splitting)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header_value",
    [
        "safe\r\nX-Injected: evil",
        "safe\nX-Injected: evil",
        "value\rSet-Cookie: session=evil",
        "\r\n",
        "Content-Length: 0\r\n\r\nHTTP/1.1 200 OK",
    ],
)
def test_validate_headers_rejects_crlf(header_value: str) -> None:
    with pytest.raises(BrimleyExecutionError, match="(?i)CR/LF|header|illegal"):
        _validate_headers({"X-Custom": header_value}, "test_func")


def test_validate_headers_accepts_safe_values() -> None:
    _validate_headers(
        {
            "Authorization": "Bearer token123",
            "Accept": "application/json",
            "X-Correlation-ID": "abc-def-123",
        },
        "fn",
    )


def test_api_runner_rejects_crlf_in_rendered_header() -> None:
    """Header injection via LLM-controlled template value."""
    func = _make_func(
        request={
            "url": "https://example.com/api",
            "method": "GET",
            "headers": {"X-Custom": "{{ user_header }}"},
        },
    )
    context = BrimleyContext()
    runner = ApiRunner()

    with patch.object(runner, "_async_request", new=AsyncMock(return_value="ok")):
        with pytest.raises(BrimleyExecutionError, match="(?i)CR/LF|header|illegal"):
            runner.run(func, {"user_header": "safe\r\nX-Evil: injected"}, context)


# ---------------------------------------------------------------------------
# Jinja2 SandboxedEnvironment — template injection prevention
# ---------------------------------------------------------------------------


def test_api_runner_uses_sandboxed_environment() -> None:
    """Static check: api_runner must use SandboxedEnvironment."""
    import inspect
    import brimley.execution.api_runner as api_module

    source = inspect.getsource(api_module)
    assert "SandboxedEnvironment" in source, (
        "api_runner.py must use jinja2.sandbox.SandboxedEnvironment for template rendering."
    )


def test_api_runner_jinja_sandbox_blocks_config_access() -> None:
    """Jinja2 sandbox must block access to ``config``, ``__class__``, etc."""
    func = _make_func(
        request={
            "url": "https://example.com/api",
            "method": "GET",
            "headers": {"X-Evil": "{{ ''.__class__.__mro__[1].__subclasses__() }}"},
        },
    )
    context = BrimleyContext()
    runner = ApiRunner()

    with patch.object(runner, "_async_request", new=AsyncMock(return_value="ok")):
        # SandboxedEnvironment raises SecurityError for unsafe attribute access
        with pytest.raises((BrimleyExecutionError, Exception)):
            runner.run(func, {}, context)


def test_api_runner_jinja_sandbox_blocks_builtin_import() -> None:
    """Sandbox must block ``__import__`` or builtins access."""
    func = _make_func(
        request={
            "url": "https://example.com/{{ __import__('os').system('id') }}",
            "method": "GET",
        },
    )
    context = BrimleyContext()
    runner = ApiRunner()

    with patch.object(runner, "_async_request", new=AsyncMock(return_value="ok")):
        with pytest.raises((BrimleyExecutionError, Exception)):
            runner.run(func, {}, context)


# ---------------------------------------------------------------------------
# CLI runner also uses SandboxedEnvironment
# ---------------------------------------------------------------------------


def test_cli_runner_uses_sandboxed_environment() -> None:
    """Static check: cli_runner must also use SandboxedEnvironment."""
    import inspect
    import brimley.execution.cli_runner as cli_module

    source = inspect.getsource(cli_module)
    assert "SandboxedEnvironment" in source, (
        "cli_runner.py must use jinja2.sandbox.SandboxedEnvironment for template rendering."
    )
