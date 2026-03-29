"""Tests for task function AST extraction and quarantine rules (B09-S5)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from brimley.core.models import PythonFunction, TaskConfig
from brimley.discovery.python_parser import parse_python_file
from brimley.discovery.scanner import BrimleyScanResult, Scanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_src(tmp_path: Path, code: str) -> Path:
    """Write a Python source file and return the path."""
    code = textwrap.dedent(code)
    f = tmp_path / "sample.py"
    f.write_text(code, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# AST extraction via parse_python_file
# ---------------------------------------------------------------------------


class TestTaskASTExtraction:
    def test_task_kwargs_extracted_to_task_config(self, tmp_path: Path) -> None:
        src = _write_src(
            tmp_path,
            """
            from brimley import function

            @function(name="my_task", task={"interval": "5m"})
            async def my_task():
                pass
            """,
        )
        results = parse_python_file(src)
        assert len(results) == 1
        fn = results[0]
        assert isinstance(fn, PythonFunction)
        assert fn.task is not None
        assert fn.task.interval == "5m"
        assert fn.task.immediate is False
        assert fn.task.retries is None

    def test_task_full_config_extracted(self, tmp_path: Path) -> None:
        src = _write_src(
            tmp_path,
            """
            from brimley import function

            @function(name="reconciler", task={"interval": "1m", "immediate": True,
                                               "retries": 3, "retry_interval": "5s exponential"})
            async def reconciler():
                pass
            """,
        )
        results = parse_python_file(src)
        fn = results[0]
        assert fn.task.interval == "1m"
        assert fn.task.immediate is True
        assert fn.task.retries == 3
        assert fn.task.retry_interval == "5s exponential"

    def test_non_task_function_has_no_task(self, tmp_path: Path) -> None:
        src = _write_src(
            tmp_path,
            """
            from brimley import function

            @function(name="plain")
            def plain(x: str) -> str:
                return x
            """,
        )
        results = parse_python_file(src)
        fn = results[0]
        assert fn.task is None

    def test_async_function_sets_is_async_true(self, tmp_path: Path) -> None:
        src = _write_src(
            tmp_path,
            """
            from brimley import function

            @function(name="async_task", task={"interval": "30s"})
            async def async_task():
                pass
            """,
        )
        results = parse_python_file(src)
        fn = results[0]
        assert fn.is_async is True

    def test_sync_function_sets_is_async_false(self, tmp_path: Path) -> None:
        src = _write_src(
            tmp_path,
            """
            from brimley import function

            @function(name="sync_fn")
            def sync_fn(x: str) -> str:
                return x
            """,
        )
        results = parse_python_file(src)
        fn = results[0]
        assert fn.is_async is False


# ---------------------------------------------------------------------------
# Scanner quarantine rules
# ---------------------------------------------------------------------------


class TestTaskQuarantineRules:
    def _scan(self, tmp_path: Path, code: str) -> BrimleyScanResult:
        _write_src(tmp_path, code)
        return Scanner(tmp_path).scan()

    # Rule 1: MCP prohibition

    def test_rule1_mcp_and_task_skipped(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function

            @function(name="bad", mcpType="tool", task={"interval": "5m"})
            async def bad():
                pass
            """,
        )
        assert not any(fn.name == "bad" for fn in result.functions)
        diags = [d for d in result.diagnostics if "bad" in d.message]
        assert diags
        assert diags[0].error_code == "ERR_TASK_QUARANTINE"
        assert "MCP" in diags[0].message or "mcpType" in diags[0].message

    # Rule 2: Signature constraint

    def test_rule2_non_injectable_param_skipped(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function

            @function(name="bad_sig", task={"interval": "5m"})
            async def bad_sig(user_value: str):
                pass
            """,
        )
        assert not any(fn.name == "bad_sig" for fn in result.functions)
        diags = [d for d in result.diagnostics if "bad_sig" in d.message]
        assert diags
        assert diags[0].error_code == "ERR_TASK_QUARANTINE"

    # Rule 3: Async validation

    def test_rule3_sync_task_skipped(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function

            @function(name="sync_task", task={"interval": "5m"})
            def sync_task():
                pass
            """,
        )
        assert not any(fn.name == "sync_task" for fn in result.functions)
        diags = [d for d in result.diagnostics if "sync_task" in d.message]
        assert diags
        assert diags[0].error_code == "ERR_TASK_QUARANTINE"
        assert "async" in diags[0].message.lower()

    # Rule 4: Interval minimum

    def test_rule4_interval_too_short_skipped(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function

            @function(name="fast_task", task={"interval": "500ms"})
            async def fast_task():
                pass
            """,
        )
        assert not any(fn.name == "fast_task" for fn in result.functions)
        diags = [d for d in result.diagnostics if "fast_task" in d.message]
        assert diags
        assert diags[0].error_code == "ERR_TASK_QUARANTINE"
        assert "minimum" in diags[0].message or "1-second" in diags[0].message

    # Valid task function — passes all rules

    def test_valid_task_function_registered(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function

            @function(name="good_task", task={"interval": "5m"})
            async def good_task():
                pass
            """,
        )
        task_fns = [fn for fn in result.functions if fn.name == "good_task"]
        assert len(task_fns) == 1
        assert task_fns[0].task.interval == "5m"
        task_diags = [d for d in result.diagnostics if "ERR_TASK_QUARANTINE" in d.error_code]
        assert not task_diags

    def test_valid_task_with_context_param_accepted(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function
            from brimley.core.context import BrimleyContext

            @function(name="ctx_task", task={"interval": "1m"})
            async def ctx_task(ctx: BrimleyContext):
                pass
            """,
        )
        task_fns = [fn for fn in result.functions if fn.name == "ctx_task"]
        assert len(task_fns) == 1

    # Other functions unaffected by quarantine

    def test_quarantine_skip_does_not_affect_other_functions(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function

            @function(name="bad_task", task={"interval": "5m"})
            def bad_task():
                pass

            @function(name="good_func")
            def good_func(x: str) -> str:
                return x
            """,
        )
        names = [fn.name for fn in result.functions]
        assert "bad_task" not in names
        assert "good_func" in names

    # Severity of quarantine diagnostic is warning, not error

    def test_quarantine_diagnostic_is_warning_severity(self, tmp_path: Path) -> None:
        result = self._scan(
            tmp_path,
            """
            from brimley import function

            @function(name="sync_bad", task={"interval": "5m"})
            def sync_bad():
                pass
            """,
        )
        diags = [d for d in result.diagnostics if d.error_code == "ERR_TASK_QUARANTINE"]
        assert diags
        assert diags[0].severity == "warning"
