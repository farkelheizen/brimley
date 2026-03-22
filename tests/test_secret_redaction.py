"""Tests for secret log redaction (B07-S18).

Covers:
- ``redact_secrets()`` utility
- Correlation-keyed secret registry (register / clear / isolation)
- Loguru sink filter scrubs registered secrets from log messages
- ``BrimleyExecutionError`` messages are scrubbed in runner error paths
- Short/empty secret values are skipped (no false positives)
"""

from __future__ import annotations

import io
import json
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from loguru import logger

from brimley.core.context import BrimleyContext
from brimley.core.models import ApiFunction, CliFunction, SecretSource
from brimley.execution.api_runner import ApiRunner
from brimley.execution.cli_runner import CliRunner
from brimley.infrastructure.logging import (
    _make_sink_filter,
    get_or_create_correlation_id,
    set_correlation_id,
)
from brimley.utils.diagnostics import BrimleyExecutionError
from brimley.utils.secrets import (
    clear_secrets,
    get_registered_secrets,
    redact_secrets,
    register_secrets,
)


# ---------------------------------------------------------------------------
# redact_secrets() utility
# ---------------------------------------------------------------------------


class TestRedactSecrets:
    def test_replaces_secret_value(self) -> None:
        assert redact_secrets("token is s3cretVal", ["s3cretVal"]) == "token is ***REDACTED***"

    def test_replaces_multiple_secrets(self) -> None:
        msg = "user=admin pass=hunter2"
        result = redact_secrets(msg, ["admin", "hunter2"])
        assert "admin" not in result
        assert "hunter2" not in result
        assert result.count("***REDACTED***") == 2

    def test_skips_short_values(self) -> None:
        assert redact_secrets("a=XY b=ok", ["XY", "ok"]) == "a=XY b=ok"

    def test_skips_empty_value(self) -> None:
        assert redact_secrets("no change", [""]) == "no change"

    def test_no_secrets_returns_unchanged(self) -> None:
        assert redact_secrets("hello world", []) == "hello world"

    def test_secret_appearing_twice(self) -> None:
        result = redact_secrets("key=abc key=abc", ["abc"])
        assert result == "key=***REDACTED*** key=***REDACTED***"

    def test_three_char_value_is_redacted(self) -> None:
        """Values with length > 2 (i.e. length 3+) ARE redacted."""
        assert redact_secrets("x=abc", ["abc"]) == "x=***REDACTED***"

    def test_two_char_value_not_redacted(self) -> None:
        """Values with length <= 2 are skipped."""
        assert redact_secrets("x=ab", ["ab"]) == "x=ab"


# ---------------------------------------------------------------------------
# Correlation-keyed secret registry
# ---------------------------------------------------------------------------


class TestSecretRegistry:
    def setup_method(self) -> None:
        # Ensure clean state before each test.
        clear_secrets("test-cid-1")
        clear_secrets("test-cid-2")

    def test_register_and_get(self) -> None:
        register_secrets("test-cid-1", ["s3cret123"])
        assert "s3cret123" in get_registered_secrets("test-cid-1")

    def test_unknown_cid_returns_empty(self) -> None:
        assert get_registered_secrets("nonexistent") == frozenset()

    def test_clear_removes_secrets(self) -> None:
        register_secrets("test-cid-1", ["s3cret123"])
        clear_secrets("test-cid-1")
        assert get_registered_secrets("test-cid-1") == frozenset()

    def test_isolation_between_correlation_ids(self) -> None:
        register_secrets("test-cid-1", ["alpha123"])
        register_secrets("test-cid-2", ["beta1234"])
        assert "alpha123" in get_registered_secrets("test-cid-1")
        assert "beta1234" not in get_registered_secrets("test-cid-1")
        assert "beta1234" in get_registered_secrets("test-cid-2")
        assert "alpha123" not in get_registered_secrets("test-cid-2")

    def test_register_skips_short_values(self) -> None:
        register_secrets("test-cid-1", ["ab", ""])
        assert get_registered_secrets("test-cid-1") == frozenset()

    def test_register_accumulates(self) -> None:
        register_secrets("test-cid-1", ["alpha123"])
        register_secrets("test-cid-1", ["beta1234"])
        secrets = get_registered_secrets("test-cid-1")
        assert "alpha123" in secrets
        assert "beta1234" in secrets

    def test_thread_safety(self) -> None:
        """Concurrent register/clear from multiple threads should not crash."""
        errors: list[Exception] = []

        def _worker(cid: str, val: str) -> None:
            try:
                for _ in range(100):
                    register_secrets(cid, [val])
                    get_registered_secrets(cid)
                clear_secrets(cid)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=_worker, args=(f"cid-{i}", f"secret-{i}-value"))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# Loguru sink filter redaction
# ---------------------------------------------------------------------------


class TestSinkFilterRedaction:
    def test_secret_scrubbed_from_log_message(self) -> None:
        """Loguru sink filter replaces registered secrets in log messages."""
        cid = "filter-test-1"
        secret_val = "SuperSecret42"

        set_correlation_id(cid)
        register_secrets(cid, [secret_val])

        sink_filter = _make_sink_filter("DEBUG", {})
        buf = io.StringIO()

        logger.remove()
        logger.add(buf, format="{message}", filter=sink_filter, level="DEBUG")

        try:
            logger.info(f"Calling API with token={secret_val}")
            output = buf.getvalue()
            assert secret_val not in output
            assert "***REDACTED***" in output
        finally:
            logger.remove()
            clear_secrets(cid)

    def test_no_secrets_registered_passes_through(self) -> None:
        """When no secrets are registered, messages pass through unchanged."""
        cid = "filter-test-2"
        set_correlation_id(cid)
        clear_secrets(cid)

        sink_filter = _make_sink_filter("DEBUG", {})
        buf = io.StringIO()

        logger.remove()
        logger.add(buf, format="{message}", filter=sink_filter, level="DEBUG")

        try:
            logger.info("No secrets here")
            output = buf.getvalue()
            assert "No secrets here" in output
            assert "***REDACTED***" not in output
        finally:
            logger.remove()


# ---------------------------------------------------------------------------
# Runner error-path redaction (ApiRunner)
# ---------------------------------------------------------------------------


def _make_api_func(**kwargs: Any) -> ApiFunction:
    defaults = {
        "name": "test_api",
        "type": "api_function",
        "return_shape": "string",
        "request": {"url": "https://example.com/api", "method": "GET"},
    }
    defaults.update(kwargs)
    return ApiFunction(**defaults)


def _make_cli_func(**kwargs: Any) -> CliFunction:
    defaults = {
        "name": "test_cli",
        "type": "cli_function",
        "return_shape": "string",
        "command": "echo",
        "timeout_seconds": 10.0,
    }
    defaults.update(kwargs)
    return CliFunction(**defaults)


class TestApiRunnerRedaction:
    def test_error_message_redacted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Secret values in error responses are scrubbed from BrimleyExecutionError."""
        secret_val = "my-api-key-12345"
        monkeypatch.setenv("API_KEY", secret_val)

        func = _make_api_func(
            secrets={"api_key": [{"env": "API_KEY"}]},
        )
        context = BrimleyContext()
        runner = ApiRunner()

        with patch.object(
            runner,
            "_async_request",
            new=AsyncMock(
                side_effect=BrimleyExecutionError(
                    message=f"Server error for key {secret_val}",
                    func_name=func.name,
                )
            ),
        ):
            with pytest.raises(BrimleyExecutionError) as exc_info:
                runner.run(func, {}, context)

        assert secret_val not in exc_info.value.message
        assert "***REDACTED***" in exc_info.value.message

    def test_secrets_cleared_after_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Secrets are cleared from the registry even on successful execution."""
        secret_val = "cleared-api-secret"
        monkeypatch.setenv("API_KEY", secret_val)

        func = _make_api_func(
            secrets={"api_key": [{"env": "API_KEY"}]},
        )
        context = BrimleyContext()
        runner = ApiRunner()

        with patch.object(runner, "_async_request", new=AsyncMock(return_value="ok")):
            runner.run(func, {}, context)

        # After run completes, secrets should be cleared for the correlation ID.
        from brimley.infrastructure.logging import get_correlation_id
        cid = get_correlation_id()
        remaining = get_registered_secrets(cid)
        assert secret_val not in remaining


# ---------------------------------------------------------------------------
# Runner error-path redaction (CliRunner)
# ---------------------------------------------------------------------------


class TestCliRunnerRedaction:
    def test_error_message_redacted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Secret values in CLI error output are scrubbed from BrimleyExecutionError."""
        secret_val = "cli-secret-xyz99"
        monkeypatch.setenv("CLI_SECRET", secret_val)

        func = _make_cli_func(
            secrets={"token": [{"env": "CLI_SECRET"}]},
            command_arguments=[],
        )
        context = BrimleyContext()
        runner = CliRunner()

        stderr_output = f"fatal: auth failed with {secret_val}"

        with patch.object(
            runner,
            "_async_exec",
            new=AsyncMock(return_value=(1, b"", stderr_output.encode())),
        ):
            with pytest.raises(BrimleyExecutionError) as exc_info:
                runner.run(func, {}, context)

        assert secret_val not in exc_info.value.message
        assert "***REDACTED***" in exc_info.value.message

    def test_secrets_cleared_after_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Secrets are cleared from the registry even on successful CLI execution."""
        secret_val = "cleared-cli-secret"
        monkeypatch.setenv("CLI_SECRET", secret_val)

        func = _make_cli_func(
            secrets={"token": [{"env": "CLI_SECRET"}]},
            command_arguments=[],
        )
        context = BrimleyContext()
        runner = CliRunner()

        with patch.object(
            runner,
            "_async_exec",
            new=AsyncMock(return_value=(0, b"ok\n", b"")),
        ):
            runner.run(func, {}, context)

        from brimley.infrastructure.logging import get_correlation_id
        cid = get_correlation_id()
        remaining = get_registered_secrets(cid)
        assert secret_val not in remaining

    def test_timeout_error_redacted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Secret values in timeout error messages are scrubbed."""
        secret_val = "timeout-secret-abc"
        monkeypatch.setenv("CLI_SECRET", secret_val)

        func = _make_cli_func(
            secrets={"token": [{"env": "CLI_SECRET"}]},
            command_arguments=[],
        )
        context = BrimleyContext()
        runner = CliRunner()

        with patch.object(
            runner,
            "_async_exec",
            new=AsyncMock(
                side_effect=BrimleyExecutionError(
                    message=f"CLI command timed out, token was {secret_val}",
                    func_name=func.name,
                )
            ),
        ):
            with pytest.raises(BrimleyExecutionError) as exc_info:
                runner.run(func, {}, context)

        assert secret_val not in exc_info.value.message
        assert "***REDACTED***" in exc_info.value.message
