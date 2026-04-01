"""test_startup.py — Tests for B09-S10: TaskScheduler startup integration.

Verifies that ``_setup_task_scheduler`` correctly wires the scheduler into the
boot path: started in repl/mcp-serve modes, not started in invoke mode, and
always registered on the container regardless of mode.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from brimley.cli.main import _setup_task_scheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task_fn(name: str) -> MagicMock:
    fn = MagicMock()
    fn.name = name
    fn.task = MagicMock()  # non-None task metadata
    return fn


def _make_non_task_fn(name: str) -> MagicMock:
    fn = MagicMock()
    fn.name = name
    fn.task = None
    return fn


def _make_context(functions=()) -> MagicMock:
    ctx = MagicMock()
    ctx.functions = list(functions)
    ctx.container = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# Tests: repl / mcp-serve mode (start=True)
# ---------------------------------------------------------------------------

class TestSetupTaskSchedulerStartMode:
    def test_scheduler_started_when_start_true(self):
        ctx = _make_context()
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            instance = MockScheduler.return_value
            _setup_task_scheduler(None, ctx, dispatcher, start=True)
            instance.start.assert_called_once()

    def test_scheduler_registered_on_container_when_started(self):
        ctx = _make_context()
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            instance = MockScheduler.return_value
            _setup_task_scheduler(None, ctx, dispatcher, start=True)
            assert ctx.container.task_scheduler is instance

    def test_task_functions_filtered_from_registry(self):
        task_fn = _make_task_fn("worker")
        non_task_fn = _make_non_task_fn("helper")
        ctx = _make_context(functions=[task_fn, non_task_fn])
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            _setup_task_scheduler(None, ctx, dispatcher, start=True)
            MockScheduler.assert_called_once_with(
                tasks=[task_fn],
                dispatcher=dispatcher,
                context=ctx,
            )

    def test_zero_task_functions_no_error(self):
        """Zero task fns: scheduler still created, start() called, no crash."""
        ctx = _make_context(functions=[_make_non_task_fn("a"), _make_non_task_fn("b")])
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            instance = MockScheduler.return_value
            _setup_task_scheduler(None, ctx, dispatcher, start=True)
            MockScheduler.assert_called_once()
            instance.start.assert_called_once()

    def test_multiple_task_functions_all_passed(self):
        fns = [_make_task_fn("t1"), _make_task_fn("t2"), _make_task_fn("t3")]
        ctx = _make_context(functions=fns)
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            _setup_task_scheduler(None, ctx, dispatcher, start=True)
            args, kwargs = MockScheduler.call_args
            assert len(kwargs["tasks"]) == 3


# ---------------------------------------------------------------------------
# Tests: invoke mode (start=False)
# ---------------------------------------------------------------------------

class TestSetupTaskSchedulerInvokeMode:
    def test_scheduler_not_started_when_start_false(self):
        ctx = _make_context()
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            instance = MockScheduler.return_value
            _setup_task_scheduler(None, ctx, dispatcher, start=False)
            instance.start.assert_not_called()

    def test_scheduler_still_registered_on_container_in_invoke_mode(self):
        ctx = _make_context()
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            instance = MockScheduler.return_value
            _setup_task_scheduler(None, ctx, dispatcher, start=False)
            assert ctx.container.task_scheduler is instance

    def test_task_functions_still_collected_in_invoke_mode(self):
        task_fn = _make_task_fn("worker")
        ctx = _make_context(functions=[task_fn])
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            _setup_task_scheduler(None, ctx, dispatcher, start=False)
            _, kwargs = MockScheduler.call_args
            assert kwargs["tasks"] == [task_fn]


# ---------------------------------------------------------------------------
# Tests: no container edge case
# ---------------------------------------------------------------------------

class TestSetupTaskSchedulerEdgeCases:
    def test_no_container_does_not_raise(self):
        """context.container is None — skip registration, no exception."""
        ctx = _make_context()
        ctx.container = None
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            _setup_task_scheduler(None, ctx, dispatcher, start=True)
            # start() still called even without container
            MockScheduler.return_value.start.assert_called_once()

    def test_dispatcher_passed_through_to_scheduler(self):
        ctx = _make_context()
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            _setup_task_scheduler(None, ctx, dispatcher, start=False)
            _, kwargs = MockScheduler.call_args
            assert kwargs["dispatcher"] is dispatcher

    def test_context_passed_through_to_scheduler(self):
        ctx = _make_context()
        dispatcher = MagicMock()
        with patch("brimley.core.task_scheduler.TaskScheduler") as MockScheduler:
            _setup_task_scheduler(None, ctx, dispatcher, start=False)
            _, kwargs = MockScheduler.call_args
            assert kwargs["context"] is ctx
