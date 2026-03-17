"""Tests for B06-S7: CLI and REPL logging controls."""
from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Optional
from typer.testing import CliRunner

import pytest

from brimley.cli.main import app, _parse_log_module_spec
from brimley.cli.repl import BrimleyREPL
from brimley.infrastructure import logging as logging_infra

runner = CliRunner()


class FakeLoguruLogger:
    def __init__(self) -> None:
        self.remove_calls: int = 0
        self.add_calls: list[dict] = []

    def remove(self) -> None:
        self.remove_calls += 1

    def add(self, sink, **kwargs) -> int:
        self.add_calls.append({"sink": sink, **kwargs})
        return len(self.add_calls)


def _combined_output(result) -> str:
    return f"{result.stdout}{getattr(result, 'stderr', '')}"


# ---------------------------------------------------------------------------
# _parse_log_module_spec unit tests
# ---------------------------------------------------------------------------

def test_parse_log_module_spec_valid() -> None:
    module, level = _parse_log_module_spec("brimley.execution:DEBUG")
    assert module == "brimley.execution"
    assert level == "DEBUG"


def test_parse_log_module_spec_normalises_level_upper() -> None:
    _, level = _parse_log_module_spec("fastmcp:warning")
    assert level == "WARNING"


def test_parse_log_module_spec_missing_colon_raises() -> None:
    import typer
    with pytest.raises(typer.BadParameter, match="MODULE:LEVEL"):
        _parse_log_module_spec("brimley_no_colon")


def test_parse_log_module_spec_invalid_level_raises() -> None:
    import typer
    with pytest.raises(typer.BadParameter, match="Invalid log level"):
        _parse_log_module_spec("brimley:VERBOSE")


def test_parse_log_module_spec_empty_module_raises() -> None:
    import typer
    with pytest.raises(typer.BadParameter, match="Module name cannot be empty"):
        _parse_log_module_spec(":DEBUG")


# ---------------------------------------------------------------------------
# CLI --log-level override tests
# ---------------------------------------------------------------------------

def test_invoke_log_level_override_passed_to_initialize(monkeypatch, tmp_path) -> None:
    import sys as _sys

    fake_logger = FakeLoguruLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    class _PinnedSys:
        stderr = _sys.stderr
        stdout = _sys.stdout

    monkeypatch.setattr(logging_infra, "sys", _PinnedSys)

    result = runner.invoke(
        app, ["invoke", "missing", "--root", str(tmp_path), "--log-level", "DEBUG"]
    )

    assert result.exit_code == 1
    assert fake_logger.remove_calls == 1
    # Sink level should reflect the CLI override
    assert fake_logger.add_calls[0]["level"] == "DEBUG"


def test_invoke_log_module_override_passed_to_filter(monkeypatch, tmp_path) -> None:
    import sys as _sys

    fake_logger = FakeLoguruLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    class _PinnedSys:
        stderr = _sys.stderr
        stdout = _sys.stdout

    monkeypatch.setattr(logging_infra, "sys", _PinnedSys)

    result = runner.invoke(
        app,
        ["invoke", "missing", "--root", str(tmp_path), "--log-module", "brimley.mcp:WARNING"],
    )

    assert result.exit_code == 1
    assert fake_logger.remove_calls == 1
    # A filter should be present on the stderr sink
    assert "filter" in fake_logger.add_calls[0]


def test_mcp_serve_log_level_override(tmp_path, monkeypatch) -> None:
    import sys as _sys

    fake_logger = FakeLoguruLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    class _PinnedSys:
        stderr = _sys.stderr
        stdout = _sys.stdout

    monkeypatch.setattr(logging_infra, "sys", _PinnedSys)

    class FakeAdapter:
        def __init__(self, registry, context):
            pass

        def discover_tools(self):
            return []

    monkeypatch.setattr("brimley.cli.main.BrimleyMCPAdapter", FakeAdapter)

    result = runner.invoke(
        app, ["mcp-serve", "--root", str(tmp_path), "--log-level", "WARNING"]
    )

    assert result.exit_code == 0
    assert fake_logger.add_calls[0]["level"] == "WARNING"


# ---------------------------------------------------------------------------
# REPL logging command tests
# ---------------------------------------------------------------------------

def _make_repl(tmp_path, monkeypatch) -> BrimleyREPL:
    """Build a minimal BrimleyREPL with logging infrastructure stubbed out."""
    fake_logger = FakeLoguruLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    repl = BrimleyREPL.__new__(BrimleyREPL)
    repl.root_dir = tmp_path
    repl.context = type("Ctx", (), {
        "settings": type("S", (), {"logging": type("L", (), {"managed": True, "level": "INFO", "modules": {}, "file": type("F", (), {"path": None})()})()})(),
        "app": {"root_dir": str(tmp_path)},
    })()
    repl._global_level_override = None
    repl._module_overrides = None
    return repl


def test_repl_cmd_log_level_global(tmp_path, monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        logging_infra,
        "initialize_logging_for_context" if hasattr(logging_infra, "initialize_logging_for_context") else "__noop",
        lambda *a, **kw: calls.append(kw),
        raising=False,
    )

    from brimley.cli.repl import BrimleyREPL
    from brimley.infrastructure.logging import initialize_logging_for_context

    captured: list[dict] = []
    monkeypatch.setattr(
        "brimley.cli.repl.initialize_logging_for_context",
        lambda ctx, **kw: captured.append(kw),
    )

    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level(["DEBUG"])

    assert result is True
    assert repl._global_level_override == "DEBUG"
    assert len(captured) == 1
    assert captured[0]["global_level_override"] == "DEBUG"


def test_repl_cmd_log_level_module(tmp_path, monkeypatch) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "brimley.cli.repl.initialize_logging_for_context",
        lambda ctx, **kw: captured.append(kw),
    )

    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level(["brimley.execution", "TRACE"])

    assert result is True
    assert repl._module_overrides == {"brimley.execution": "TRACE"}
    assert captured[0]["module_overrides"] == {"brimley.execution": "TRACE"}


def test_repl_cmd_log_level_invalid_level(tmp_path, monkeypatch) -> None:
    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level(["VERBOSELY"])
    assert result is True  # returns True to continue REPL
    # global level should remain unchanged
    assert repl._global_level_override is None


def test_repl_cmd_log_level_no_args(tmp_path, monkeypatch) -> None:
    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level([])
    assert result is True


def test_repl_cmd_log_modules_empty(tmp_path, monkeypatch) -> None:
    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_modules([])
    assert result is True


def test_repl_cmd_log_modules_shows_overrides(tmp_path, monkeypatch) -> None:
    repl = _make_repl(tmp_path, monkeypatch)
    repl._module_overrides = {"brimley": "DEBUG"}
    result = repl._cmd_log_modules([])
    assert result is True


def test_repl_cmd_log_reset(tmp_path, monkeypatch) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "brimley.cli.repl.initialize_logging_for_context",
        lambda ctx, **kw: captured.append(kw),
    )

    repl = _make_repl(tmp_path, monkeypatch)
    repl._global_level_override = "DEBUG"
    repl._module_overrides = {"brimley": "TRACE"}

    result = repl._cmd_log_reset([])

    assert result is True
    assert repl._global_level_override is None
    assert repl._module_overrides is None
    # Should call initialize without overrides
    assert len(captured) == 1
    assert captured[0] == {}


def test_repl_cmd_log_level_for_id_sets_override(tmp_path, monkeypatch) -> None:
    with logging_infra._overrides_lock:
        logging_infra._correlation_overrides.clear()

    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level_for_id(["test-cid-1", "DEBUG"])

    assert result is True
    assert logging_infra.get_correlation_overrides().get("test-cid-1") == "DEBUG"

    # Cleanup
    logging_infra.clear_correlation_level_override("test-cid-1")


def test_repl_cmd_log_level_for_id_clear(tmp_path, monkeypatch) -> None:
    logging_infra.set_correlation_level_override("test-cid-2", "DEBUG")

    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level_for_id(["test-cid-2", "--clear"])

    assert result is True
    assert "test-cid-2" not in logging_infra.get_correlation_overrides()


def test_repl_cmd_log_level_for_id_invalid_level(tmp_path, monkeypatch) -> None:
    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level_for_id(["cid", "BADLEVEL"])
    assert result is True
    assert "cid" not in logging_infra.get_correlation_overrides()


def test_repl_cmd_log_level_for_id_no_args(tmp_path, monkeypatch) -> None:
    repl = _make_repl(tmp_path, monkeypatch)
    result = repl._cmd_log_level_for_id(["only-one"])
    assert result is True
