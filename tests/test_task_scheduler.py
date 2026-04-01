"""Tests for TaskScheduler: B09-S6 (core), B09-S7 (retry), B09-S8 (overlap).

All tests use very short intervals (50 ms) and explicit threading events to avoid
flakiness without relying on wall-clock sleeps.
"""

from __future__ import annotations

import threading
import time
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from brimley.core.models import PythonFunction, TaskConfig
from brimley.core.task_scheduler import TaskScheduler, _compute_backoff
from brimley.utils.time_parser import RetryIntervalConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task_func(
    name: str = "my_task",
    interval: str = "1s",
    immediate: bool = False,
    retries: int | None = None,
    retry_interval: str = "1s",
) -> PythonFunction:
    return PythonFunction(
        name=name,
        type="python_function",
        return_shape="void",
        handler="mymod.my_task",
        task=TaskConfig(
            interval=interval,
            immediate=immediate,
            retries=retries,
            retry_interval=retry_interval,
        ),
        is_async=True,
    )


def _make_scheduler(
    tasks: List[PythonFunction],
    dispatcher_run=None,
) -> TaskScheduler:
    dispatcher = MagicMock()
    if dispatcher_run is not None:
        dispatcher.run = dispatcher_run
    context = MagicMock()
    return TaskScheduler(tasks=tasks, dispatcher=dispatcher, context=context)


def _wait_for(condition, *, timeout: float = 3.0, poll: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(poll)
    return False


# ---------------------------------------------------------------------------
# B09-S6: TaskScheduler core
# ---------------------------------------------------------------------------

class TestTaskSchedulerCore:
    def test_start_sets_started_flag(self):
        sched = _make_scheduler(tasks=[])
        assert not sched._started
        sched.start()
        try:
            assert sched._started
        finally:
            sched.stop()

    def test_start_creates_daemon_thread(self):
        sched = _make_scheduler(tasks=[])
        sched.start()
        try:
            assert sched._thread is not None
            assert sched._thread.daemon
        finally:
            sched.stop()

    def test_start_is_idempotent(self):
        sched = _make_scheduler(tasks=[])
        sched.start()
        thread_before = sched._thread
        sched.start()  # second call — should not create another thread
        try:
            assert sched._thread is thread_before
        finally:
            sched.stop()

    def test_stop_before_start_is_noop(self):
        """In invoke mode, stop() on a non-started scheduler should not error."""
        sched = _make_scheduler(tasks=[])
        sched.stop()  # must not raise

    def test_stop_after_start_is_clean(self):
        sched = _make_scheduler(tasks=[])
        sched.start()
        sched.stop()  # must not raise

    def test_event_loop_created_on_daemon_thread(self):
        sched = _make_scheduler(tasks=[])
        sched.start()
        try:
            assert sched._loop is not None
        finally:
            sched.stop()

    def test_no_tasks_start_stop_clean(self):
        """Scheduler with zero task functions completes without error."""
        sched = _make_scheduler(tasks=[])
        sched.start()
        sched.stop()  # immediate — nothing to cancel

    def test_task_states_populated_for_task_functions(self):
        func = _make_task_func()
        sched = _make_scheduler(tasks=[func])
        sched.start()
        try:
            assert "my_task" in sched._task_states
        finally:
            sched.stop()

    def test_non_task_functions_filtered_out(self):
        """Functions without task= metadata are silently excluded."""
        func = PythonFunction(
            name="plain_fn",
            type="python_function",
            return_shape="void",
            handler="mymod.plain_fn",
        )
        sched = _make_scheduler(tasks=[func])
        sched.start()
        try:
            assert "plain_fn" not in sched._task_states
        finally:
            sched.stop()

    def test_immediate_task_executes_without_initial_delay(self):
        """immediate=True → dispatcher.run called quickly (< 0.5 s)."""
        called = threading.Event()

        def dispatch_run(func, args, ctx):
            called.set()

        func = _make_task_func(name="fast", interval="60s", immediate=True)
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        sched.start()
        try:
            assert called.wait(timeout=1.0), "immediate task was not called within 1 s"
        finally:
            sched.stop()

    def test_non_immediate_task_waits_before_first_execution(self):
        """immediate=False → dispatcher.run not called immediately."""
        called = threading.Event()

        def dispatch_run(func, args, ctx):
            called.set()

        # 10-second interval — should not fire during 0.2 s window
        func = _make_task_func(name="slow", interval="10s", immediate=False)
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        sched.start()
        try:
            assert not called.wait(timeout=0.2), "non-immediate task fired too early"
        finally:
            sched.stop()

    def test_get_task_status_returns_all_tasks(self):
        funcs = [_make_task_func(name=f"t{i}", interval="60s") for i in range(3)]
        sched = _make_scheduler(tasks=funcs)
        sched.start()
        try:
            # Wait for _task_states to populate
            assert _wait_for(lambda: len(sched._task_states) == 3)
            statuses = sched.get_task_status()
            names = {s["name"] for s in statuses}
            assert names == {"t0", "t1", "t2"}
        finally:
            sched.stop()

    def test_get_task_status_columns(self):
        func = _make_task_func(name="col_task", interval="5m", immediate=True)
        executed = threading.Event()

        def dispatch_run(f, args, ctx):
            executed.set()

        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        sched.start()
        try:
            executed.wait(timeout=1.0)
            statuses = sched.get_task_status()
            row = statuses[0]
            assert "name" in row
            assert "interval" in row
            assert "status" in row
            assert "last_run" in row
            assert "next_run" in row
            assert "consecutive_failure_count" in row
            assert "consecutive_skip_count" in row
        finally:
            sched.stop()

    def test_get_task_status_empty_when_no_tasks(self):
        sched = _make_scheduler(tasks=[])
        sched.start()
        try:
            assert sched.get_task_status() == []
        finally:
            sched.stop()

    def test_last_run_updated_after_execution(self):
        func = _make_task_func(name="ran", interval="60s", immediate=True)
        executed = threading.Event()

        def dispatch_run(f, args, ctx):
            executed.set()

        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        sched.start()
        try:
            executed.wait(timeout=1.0)
            time.sleep(0.05)  # allow state to propagate
            row = sched.get_task_status()[0]
            assert row["last_run"] is not None
        finally:
            sched.stop()


# ---------------------------------------------------------------------------
# B09-S7: Retry policy
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    """Tests using _compute_backoff directly (pure logic, no threading)."""

    # --- Fixed strategy -------------------------------------------------------

    def test_fixed_constant_delay(self):
        cfg = RetryIntervalConfig(base=10.0, strategy="fixed")
        assert _compute_backoff(0, cfg, 60.0) == 10.0
        assert _compute_backoff(1, cfg, 60.0) == 10.0
        assert _compute_backoff(5, cfg, 60.0) == 10.0

    def test_fixed_capped_at_interval(self):
        cfg = RetryIntervalConfig(base=30.0, strategy="fixed")
        assert _compute_backoff(0, cfg, 20.0) == 20.0

    # --- Exponential strategy -------------------------------------------------

    def test_exponential_doubles(self):
        cfg = RetryIntervalConfig(base=10.0, strategy="exponential")
        assert _compute_backoff(0, cfg, 9999.0) == 10.0   # base * 2^0
        assert _compute_backoff(1, cfg, 9999.0) == 20.0   # base * 2^1
        assert _compute_backoff(2, cfg, 9999.0) == 40.0   # base * 2^2
        assert _compute_backoff(3, cfg, 9999.0) == 80.0   # base * 2^3

    def test_exponential_capped_at_interval(self):
        cfg = RetryIntervalConfig(base=10.0, strategy="exponential")
        assert _compute_backoff(5, cfg, 50.0) == 50.0     # 320 capped

    # --- Multiplier strategy --------------------------------------------------

    def test_multiplier_applies_factor(self):
        cfg = RetryIntervalConfig(base=10.0, strategy="multiplier", factor=1.5)
        assert _compute_backoff(0, cfg, 9999.0) == pytest.approx(10.0)
        assert _compute_backoff(1, cfg, 9999.0) == pytest.approx(15.0)
        assert _compute_backoff(2, cfg, 9999.0) == pytest.approx(22.5)

    def test_multiplier_capped_at_interval(self):
        cfg = RetryIntervalConfig(base=10.0, strategy="multiplier", factor=2.0)
        assert _compute_backoff(4, cfg, 30.0) == 30.0     # 160 capped

    def test_multiplier_default_factor(self):
        """Factor=None should fall back to 1.5."""
        cfg = RetryIntervalConfig(base=10.0, strategy="multiplier", factor=None)
        assert _compute_backoff(1, cfg, 9999.0) == pytest.approx(15.0)

    # --- No retry config ------------------------------------------------------

    def test_no_retry_cfg_returns_min_1s(self):
        assert _compute_backoff(0, None, 60.0) == 1.0

    def test_no_retry_cfg_capped_at_interval_below_1s(self):
        assert _compute_backoff(0, None, 0.5) == 0.5

    # --- Integration: retry fires after failure -------------------------------

    def test_retry_fires_after_immediate_task_fails(self):
        """Verify that after a failure, the task is retried (atomic execution counter)."""
        call_results = [False, True]  # fail, then succeed
        call_count = [0]
        done = threading.Event()

        def dispatch_run(func, args, ctx):
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(call_results):
                if not call_results[idx]:
                    raise RuntimeError("simulated failure")
            done.set()

        func = _make_task_func(
            name="retry_task",
            interval="60s",
            immediate=True,
            retries=3,
            retry_interval="0s",  # 0s ⇒ parse_duration raises; use 1ms instead
        )
        # Use 1ms retry_interval to keep the test fast
        func = _make_task_func(
            name="retry_task",
            interval="60s",
            immediate=True,
            retries=3,
            retry_interval="1s",
        )
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        # Patch _compute_backoff to return 0 so retries are instant
        with patch("brimley.core.task_scheduler._compute_backoff", return_value=0.02):
            sched.start()
            try:
                assert done.wait(timeout=3.0), "retry did not complete within 3 s"
                assert call_count[0] >= 2
            finally:
                sched.stop()

    def test_retry_counter_resets_on_success(self):
        """After a success, the retry_count in _TaskState resets to 0."""
        call_count = [0]
        done = threading.Event()

        def dispatch_run(func, args, ctx):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first call fails")
            done.set()

        func = _make_task_func(name="reset_task", interval="60s", immediate=True, retries=5)
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        with patch("brimley.core.task_scheduler._compute_backoff", return_value=0.02):
            sched.start()
            try:
                assert done.wait(timeout=3.0)
                # Allow state to propagate
                time.sleep(0.05)
                state = sched._task_states["reset_task"]
                assert state.retry_count == 0
            finally:
                sched.stop()

    def test_retries_exhausted_resets_not_loops_immediately(self):
        """After max retries, retry_count resets (not stuck in failure loop)."""
        call_count = [0]

        def dispatch_run(func, args, ctx):
            call_count[0] += 1
            raise RuntimeError("always fails")

        # retries=2: fail, retry, retry, exhausted → wait interval
        func = _make_task_func(name="exhausted_task", interval="60s", immediate=True, retries=2)
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        with patch("brimley.core.task_scheduler._compute_backoff", return_value=0.02):
            sched.start()
            try:
                # Wait for 3 calls (1 initial + 2 retries)
                assert _wait_for(lambda: call_count[0] >= 3, timeout=3.0)
                time.sleep(0.1)  # let exhaustion handling run
                state = sched._task_states["exhausted_task"]
                # After exhaustion, retry_count is reset to 0 and status is waiting
                assert state.retry_count == 0
                assert state.status in ("waiting", "backoff")
            finally:
                sched.stop()


# ---------------------------------------------------------------------------
# B09-S8: Overlap prevention
# ---------------------------------------------------------------------------

class TestOverlapPrevention:
    def test_overlapping_iteration_is_skipped(self):
        """If a task is still running, the next scheduled tick skips launching a new iteration."""
        running = threading.Event()
        release = threading.Event()
        call_count = [0]

        def dispatch_run(func, args, ctx):
            call_count[0] += 1
            if call_count[0] == 1:
                running.set()
                release.wait(timeout=2.0)
            # subsequent calls return immediately

        # interval=0.05s so the scheduler ticks often
        func = _make_task_func(name="ov_task", interval="0.05s", immediate=True)
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        sched.start()
        try:
            running.wait(timeout=1.0)  # first iteration started
            time.sleep(0.2)  # let scheduler tick 3+ times while first is "running"
            state = sched._task_states["ov_task"]
            assert state.consecutive_skip_count > 0, "expected at least one skip"
        finally:
            release.set()
            sched.stop()

    def test_skip_warning_emitted_after_3_consecutive_skips(self):
        """WARNING emitted when consecutive_skip_count reaches 3."""
        running = threading.Event()
        release = threading.Event()

        def dispatch_run(func, args, ctx):
            running.set()
            release.wait(timeout=5.0)

        func = _make_task_func(name="warn_task", interval="0.05s", immediate=True)
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        with patch("brimley.core.task_scheduler._logger") as mock_log:
            sched.start()
            try:
                running.wait(timeout=1.0)
                # Give the scheduler time to accumulate ≥ 3 skip warnings
                assert _wait_for(
                    lambda: any(
                        "consecutive iterations" in str(c)
                        for c in mock_log.warning.call_args_list
                    ),
                    timeout=3.0,
                ), "Expected warning after 3 consecutive skips"
            finally:
                release.set()
                sched.stop()

    def test_skip_counter_resets_after_successful_completion(self):
        """After the long-running iteration finishes, the skip counter resets."""
        call_count = [0]
        running = threading.Event()
        release = threading.Event()

        def dispatch_run(func, args, ctx):
            call_count[0] += 1
            if call_count[0] == 1:
                running.set()
                release.wait(timeout=2.0)
            # subsequent calls complete quickly

        func = _make_task_func(name="reset_skip", interval="0.05s", immediate=True)
        sched = _make_scheduler(tasks=[func], dispatcher_run=dispatch_run)
        sched.start()
        try:
            running.wait(timeout=1.0)
            time.sleep(0.2)  # accumulate some skips
            state = sched._task_states["reset_skip"]
            assert state.consecutive_skip_count > 0
            release.set()   # let the first iteration finish

            # Give the scheduler clock a tick to reset the skip counter
            # (reset happens on the next successful non-skip tick)
            assert _wait_for(
                lambda: sched._task_states["reset_skip"].consecutive_skip_count == 0,
                timeout=3.0,
            ), "skip counter was not reset after iteration completed"
        finally:
            sched.stop()


# ---------------------------------------------------------------------------
# _compute_backoff edge cases
# ---------------------------------------------------------------------------

class TestComputeBackoff:
    def test_backoff_never_exceeds_interval(self):
        cfg = RetryIntervalConfig(base=100.0, strategy="exponential")
        for n in range(10):
            assert _compute_backoff(n, cfg, 60.0) <= 60.0

    def test_backoff_at_zero_retry_count(self):
        cfg = RetryIntervalConfig(base=5.0, strategy="fixed")
        assert _compute_backoff(0, cfg, 60.0) == 5.0

    def test_backoff_with_interval_shorter_than_base(self):
        cfg = RetryIntervalConfig(base=30.0, strategy="fixed")
        assert _compute_backoff(0, cfg, 10.0) == 10.0
