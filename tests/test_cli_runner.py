"""Tests for CliRunner (Brimley 0.7)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brimley.core.context import BrimleyContext
from brimley.core.models import CliFunction
from brimley.execution.cli_runner import CliRunner, _parse_output
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
# can_handle
# ---------------------------------------------------------------------------


def test_cli_runner_can_handle() -> None:
    runner = CliRunner()
    func = _make_func()
    assert runner.can_handle(func) is True


def test_cli_runner_cannot_handle_api_function() -> None:
    from brimley.core.models import ApiFunction
    runner = CliRunner()
    func = ApiFunction(name="fn", type="api_function", return_shape="string", request={"url": "https://x.com"})
    assert runner.can_handle(func) is False


# ---------------------------------------------------------------------------
# _parse_output
# ---------------------------------------------------------------------------


def test_parse_output_text_passthrough() -> None:
    from brimley.core.models import CliParsingConfig
    cfg = CliParsingConfig(strategy="text")
    assert _parse_output("hello world\n", cfg, "fn") == "hello world\n"


def test_parse_output_json_valid() -> None:
    from brimley.core.models import CliParsingConfig
    cfg = CliParsingConfig(strategy="json")
    result = _parse_output('{"key": "val"}', cfg, "fn")
    assert result == {"key": "val"}


def test_parse_output_json_invalid_raises() -> None:
    from brimley.core.models import CliParsingConfig
    cfg = CliParsingConfig(strategy="json")
    with pytest.raises(BrimleyExecutionError, match="JSON"):
        _parse_output("not-json", cfg, "fn")


def test_parse_output_regex_match() -> None:
    from brimley.core.models import CliParsingConfig
    cfg = CliParsingConfig(
        strategy="regex",
        pattern=r"load average: (?P<val>\d+\.\d+)",
        capture_group="val",
    )
    result = _parse_output("14:30  up 5 days, load average: 1.23, 0.87, 0.62", cfg, "fn")
    assert result == "1.23"


def test_parse_output_regex_no_match_raises() -> None:
    from brimley.core.models import CliParsingConfig
    cfg = CliParsingConfig(strategy="regex", pattern=r"IMPOSSIBLE_PATTERN_XYZ")
    with pytest.raises(BrimleyExecutionError, match="did not match"):
        _parse_output("no match here", cfg, "fn")


def test_parse_output_regex_no_pattern_raises() -> None:
    from brimley.core.models import CliParsingConfig
    cfg = CliParsingConfig(strategy="regex")
    with pytest.raises(BrimleyExecutionError, match="pattern"):
        _parse_output("stdout", cfg, "fn")


def test_parse_output_regex_whole_match_when_no_capture_group() -> None:
    from brimley.core.models import CliParsingConfig
    cfg = CliParsingConfig(strategy="regex", pattern=r"\d+\.\d+")
    result = _parse_output("1.23 4.56", cfg, "fn")
    assert result == "1.23"


# ---------------------------------------------------------------------------
# CliRunner.run — via mocked _async_exec
# ---------------------------------------------------------------------------


def test_cli_runner_run_returns_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func()
    context = BrimleyContext()
    runner = CliRunner()

    with patch.object(runner, "_async_exec", new=AsyncMock(return_value=(0, b"hello\n", b""))):
        result = runner.run(func, {}, context)
    assert result == "hello\n"


def test_cli_runner_run_applies_text_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func()
    context = BrimleyContext()
    runner = CliRunner()

    with patch.object(runner, "_async_exec", new=AsyncMock(return_value=(0, b"raw output\n", b""))):
        result = runner.run(func, {}, context)
    assert result == "raw output\n"


def test_cli_runner_run_applies_json_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func(parsing={"strategy": "json"}, return_shape="dict")
    context = BrimleyContext()
    runner = CliRunner()

    with patch.object(runner, "_async_exec", new=AsyncMock(return_value=(0, b'{"status":"ok"}', b""))):
        result = runner.run(func, {}, context)
    assert result == {"status": "ok"}


def test_cli_runner_run_injects_args(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func(args=["{{ name }}", "extra"])
    context = BrimleyContext()
    runner = CliRunner()

    captured: dict = {}

    async def fake_exec(f, rendered_args, env, cwd):
        captured["args"] = rendered_args
        return (0, b"ok", b"")

    with patch.object(runner, "_async_exec", side_effect=fake_exec):
        runner.run(func, {"name": "world"}, context)

    assert captured["args"] == ["world", "extra"]


def test_cli_runner_run_undefined_template_arg_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func(args=["{{ undefined_var }}"])
    context = BrimleyContext()
    runner = CliRunner()

    with patch.object(runner, "_async_exec", new=AsyncMock(return_value=(0, b"ok", b""))):
        with pytest.raises(BrimleyExecutionError, match="Arg template rendering failed"):
            runner.run(func, {}, context)


def test_cli_runner_run_resolves_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_KEY", "keyvalue")
    func = _make_func(
        args=["{{ secrets.key }}"],
        secrets={"key": [{"env": "MY_KEY"}]},
    )
    context = BrimleyContext()
    runner = CliRunner()

    captured: dict = {}

    async def fake_exec(f, rendered_args, env, cwd):
        captured["args"] = rendered_args
        return (0, b"ok", b"")

    with patch.object(runner, "_async_exec", side_effect=fake_exec):
        runner.run(func, {}, context)

    assert captured["args"] == ["keyvalue"]


def test_cli_runner_run_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING", raising=False)
    func = _make_func(secrets={"key": [{"env": "MISSING"}]})
    context = BrimleyContext()
    runner = CliRunner()

    with pytest.raises(BrimleyExecutionError):
        runner.run(func, {}, context)


def test_cli_runner_run_env_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func(env={"DEBUG_MODE": "{{ flag }}"})
    context = BrimleyContext()
    runner = CliRunner()

    captured: dict = {}

    async def fake_exec(f, rendered_args, subprocess_env, cwd):
        captured["env"] = subprocess_env
        return (0, b"ok", b"")

    with patch.object(runner, "_async_exec", side_effect=fake_exec):
        runner.run(func, {"flag": "true"}, context)

    assert captured["env"] == {"DEBUG_MODE": "true"}


def test_cli_runner_run_cwd_defaults_to_project_root() -> None:
    func = _make_func()
    context = BrimleyContext()
    context.app["root_dir"] = "/fake/root"
    runner = CliRunner()

    captured: dict = {}

    async def fake_exec(f, rendered_args, subprocess_env, cwd):
        captured["cwd"] = cwd
        return (0, b"ok", b"")

    with patch.object(runner, "_async_exec", side_effect=fake_exec):
        runner.run(func, {}, context)

    assert captured["cwd"] == "/fake/root"


def test_cli_runner_run_explicit_cwd_respected() -> None:
    func = _make_func(cwd="/explicit/path")
    context = BrimleyContext()
    runner = CliRunner()

    captured: dict = {}

    async def fake_exec(f, rendered_args, subprocess_env, cwd):
        captured["cwd"] = cwd
        return (0, b"ok", b"")

    with patch.object(runner, "_async_exec", side_effect=fake_exec):
        runner.run(func, {}, context)

    assert captured["cwd"] == "/explicit/path"


# ---------------------------------------------------------------------------
# Dispatcher integration
# ---------------------------------------------------------------------------


def test_dispatcher_routes_cli_function() -> None:
    from brimley.execution.dispatcher import Dispatcher
    dispatcher = Dispatcher()
    context = BrimleyContext()

    func = _make_func(name="dispatch_cli")
    captured: dict = {}

    def fake_run(f, args, ctx):
        captured["func"] = f
        return "done"

    dispatcher.cli_runner.run = fake_run  # type: ignore[method-assign]

    result = dispatcher.run(func, {}, context)
    assert result == "done"
    assert captured["func"] is func


def test_dispatcher_routes_api_function() -> None:
    from brimley.core.models import ApiFunction
    from brimley.execution.dispatcher import Dispatcher
    dispatcher = Dispatcher()
    context = BrimleyContext()

    func = ApiFunction(
        name="dispatch_api",
        type="api_function",
        return_shape="primitive",
        request={"url": "https://example.com"},
    )
    captured: dict = {}

    def fake_run(f, args, ctx):
        captured["func"] = f
        return {"ok": True}

    dispatcher.api_runner.run = fake_run  # type: ignore[method-assign]

    result = dispatcher.run(func, {}, context)
    assert result == {"ok": True}
    assert captured["func"] is func
