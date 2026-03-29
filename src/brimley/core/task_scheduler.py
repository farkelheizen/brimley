"""task_scheduler.py — Managed task scheduling for Brimley (v0.9).

Runs on a dedicated daemon thread with its own asyncio event loop. Task functions
declared with ``@function(task={...})`` are discovered during boot and driven here.

Lifecycle (see B09-S9/S10 for integration):
  1. ``TaskScheduler(tasks, dispatcher, context)`` — constructed after boot
  2. ``start()`` — launched after ``@on_startup`` hooks; repl / mcp-serve only
  3. ``stop()`` — phase-1 of three-phase shutdown

Retry policy (B09-S7): per-task ``retry_interval`` drives exponential, multiplier,
or fixed backoff, capped at the task's own ``interval``.

Overlap prevention (B09-S8): an ``asyncio.Lock`` per task ensures at most one
iteration runs at a time.  Scheduled iterations that arrive while the lock is held
are skipped (not queued).  A WARNING is emitted after 3 consecutive skips.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger as _logger

from brimley.core.models import PythonFunction
from brimley.utils.time_parser import RetryIntervalConfig, parse_duration, parse_retry_interval

if TYPE_CHECKING:
    from brimley.core.context import BrimleyContext
    from brimley.execution.dispatcher import Dispatcher


_GRACE_SECONDS = 30


# ---------------------------------------------------------------------------
# Internal per-task runtime state
# ---------------------------------------------------------------------------

@dataclass
class _TaskState:
    """Mutable runtime state for a single scheduled task.

    All fields are only read/written from the scheduler's event loop unless
    otherwise specified.
    """

    func: PythonFunction
    # B09-S8: Overlap guard — True while an iteration (incl. retries) is active
    is_executing: bool = False
    consecutive_skip_count: int = 0
    # B09-S7: Retry state (reset by _run_iteration on success / exhaustion)
    retry_count: int = 0
    consecutive_failure_count: int = 0
    # Introspection (read by get_task_status())
    status: str = "waiting"   # "running" | "waiting" | "backoff"
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    asyncio_task: Optional["asyncio.Task[None]"] = None   # scheduler clock task


# ---------------------------------------------------------------------------
# TaskScheduler
# ---------------------------------------------------------------------------

class TaskScheduler:
    """Runs task functions on a dedicated daemon thread with its own event loop.

    Public interface:
    - :meth:`start` / :meth:`stop` — lifecycle integration (B09-S10 / B09-S9)
    - :meth:`get_task_status` — REPL ``/tasks`` command (B09-S11)
    """

    def __init__(
        self,
        tasks: List[PythonFunction],
        dispatcher: "Dispatcher",
        context: "BrimleyContext",
    ) -> None:
        self._tasks = [t for t in tasks if t.task is not None]
        self._dispatcher = dispatcher
        self._context = context
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._task_states: Dict[str, _TaskState] = {}
        self._started = False
        # asyncio.Event created inside the event loop thread (see _main)
        self._shutdown_event: Optional[asyncio.Event] = None
        # Tracks fire-and-forget execution Tasks for clean shutdown
        self._exec_tasks: Optional[set] = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Public lifecycle API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the scheduler daemon thread. No-op if already started."""
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="brimley-task-scheduler",
        )
        self._thread.start()
        # Wait up to 5 s for the event loop to initialise before returning.
        self._ready.wait(timeout=5)
        _logger.info(
            "[TaskScheduler] Started with {} task(s).", len(self._task_states)
        )

    def stop(self) -> None:
        """Cancel all running task coroutines (30 s grace, then hard-cancel)."""
        if not self._started or self._loop is None or self._loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(self._shutdown_coro(), self._loop)
        try:
            future.result(timeout=_GRACE_SECONDS + 5)
        except Exception as exc:
            _logger.warning(
                "[TaskScheduler] stop() encountered an error during shutdown: {}", exc
            )
        _logger.info("[TaskScheduler] Stopped.")

    def get_task_status(self) -> List[Dict[str, Any]]:
        """Return a snapshot of scheduling state for all registered tasks.

        Called from the REPL thread; reads volatile state without locking —
        values are advisory.
        """
        return [
            {
                "name": name,
                "interval": state.func.task.interval if state.func.task else None,
                "status": state.status,
                "last_run": state.last_run.isoformat() if state.last_run else None,
                "next_run": state.next_run.isoformat() if state.next_run else None,
                "consecutive_failure_count": state.consecutive_failure_count,
                "consecutive_skip_count": state.consecutive_skip_count,
            }
            for name, state in self._task_states.items()
        ]

    # ------------------------------------------------------------------
    # Internal: daemon thread + event loop bootstrap
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    async def _main(self) -> None:
        """Initialise per-task state and launch all scheduler clock coroutines."""
        self._shutdown_event = asyncio.Event()
        self._exec_tasks = set()

        for func in self._tasks:
            state = _TaskState(func=func)
            self._task_states[func.name] = state

        # Signal start() that the loop is ready.
        self._ready.set()

        # Launch one clock coroutine per task.
        for state in self._task_states.values():
            task = asyncio.get_event_loop().create_task(
                self._task_clock(state), name=f"clock:{state.func.name}"
            )
            state.asyncio_task = task

        # Block until stop() signals via _shutdown_coro().
        await self._shutdown_event.wait()

    async def _shutdown_coro(self) -> None:
        """Cancel all scheduler and execution tasks; signal _main() to exit."""
        clock_tasks = [
            s.asyncio_task
            for s in self._task_states.values()
            if s.asyncio_task is not None
        ]
        exec_tasks = list(self._exec_tasks) if self._exec_tasks else []
        all_tasks = clock_tasks + exec_tasks

        for t in all_tasks:
            t.cancel()

        if all_tasks:
            _done, pending = await asyncio.wait(all_tasks, timeout=_GRACE_SECONDS)
            for t in pending:
                _logger.warning(
                    "[TaskScheduler] Hard-cancelling task '{}' after {}s grace period.",
                    t.get_name(),
                    _GRACE_SECONDS,
                )
                t.cancel()

        # Release _main() from its wait so the event loop can exit cleanly.
        if self._shutdown_event is not None:
            self._shutdown_event.set()

    # ------------------------------------------------------------------
    # Internal: clock coroutine (B09-S6 scheduling + B09-S8 overlap guard)
    # ------------------------------------------------------------------

    async def _task_clock(self, state: _TaskState) -> None:
        """Clock coroutine: ticks every interval, skips if previous is still running."""
        assert state.func.task is not None
        task_cfg = state.func.task
        interval_seconds = parse_duration(task_cfg.interval)

        # immediate=True: fire first iteration now, before the first sleep.
        if task_cfg.immediate:
            self._fire_iteration(state, interval_seconds)

        while True:
            state.status = "waiting"
            state.next_run = _now_plus(interval_seconds)
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                return

            # B09-S8: Overlap guard
            if state.is_executing:
                state.consecutive_skip_count += 1
                if state.consecutive_skip_count >= 3:
                    _logger.warning(
                        "[TaskScheduler] Task '{}' has been running longer than its "
                        "interval for {} consecutive iterations. Consider increasing "
                        "the interval or optimizing the task logic.",
                        state.func.name,
                        state.consecutive_skip_count,
                    )
            else:
                # Previous iteration completed in time — reset skip counter and schedule.
                state.consecutive_skip_count = 0
                self._fire_iteration(state, interval_seconds)

    def _fire_iteration(self, state: _TaskState, interval_seconds: float) -> None:
        """Launch a new execution task for the given task state (fire-and-forget)."""
        loop = asyncio.get_event_loop()
        t = loop.create_task(
            self._run_iteration(state, interval_seconds),
            name=f"exec:{state.func.name}",
        )
        if self._exec_tasks is not None:
            self._exec_tasks.add(t)
            t.add_done_callback(self._exec_tasks.discard)

    # ------------------------------------------------------------------
    # Internal: iteration execution with retry (B09-S7)
    # ------------------------------------------------------------------

    async def _run_iteration(self, state: _TaskState, interval_seconds: float) -> None:
        """Execute one iteration with the configured retry policy."""
        assert state.func.task is not None
        task_cfg = state.func.task
        retry_cfg = (
            parse_retry_interval(task_cfg.retry_interval)
            if task_cfg.retry_interval
            else None
        )
        max_retries = task_cfg.retries  # None → unlimited

        state.is_executing = True
        try:
            while True:
                state.status = "running"
                state.last_run = datetime.now()
                success = await self._execute_one(state)

                if success:
                    state.consecutive_skip_count = 0
                    state.retry_count = 0
                    state.consecutive_failure_count = 0
                    state.status = "waiting"
                    return

                # Failure handling
                state.consecutive_failure_count += 1

                if max_retries is not None and state.retry_count >= max_retries:
                    _logger.warning(
                        "[TaskScheduler] Task '{}' exhausted {} retries. "
                        "Waiting for next scheduled interval.",
                        state.func.name,
                        max_retries,
                    )
                    state.retry_count = 0
                    state.status = "waiting"
                    return

                backoff = _compute_backoff(state.retry_count, retry_cfg, interval_seconds)
                state.retry_count += 1
                state.status = "backoff"
                _logger.warning(
                    "[TaskScheduler] Task '{}' failed (attempt {}). Retrying in {:.1f}s.",
                    state.func.name,
                    state.retry_count,
                    backoff,
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    return
        finally:
            state.is_executing = False

    async def _execute_one(self, state: _TaskState) -> bool:
        """Run one iteration of the task function. Returns True on success."""
        func = state.func
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self._dispatcher.run,
                func,
                {},
                self._context,
            )
            _logger.debug(
                "[TaskScheduler] Task '{}' iteration completed.", func.name
            )
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _logger.error(
                "[TaskScheduler] Task '{}' iteration raised an exception: {}",
                func.name,
                exc,
            )
            return False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _now_plus(seconds: float) -> datetime:
    from datetime import timedelta
    return datetime.now() + timedelta(seconds=seconds)


def _compute_backoff(
    retry_count: int,
    retry_cfg: Optional[RetryIntervalConfig],
    interval_seconds: float,
) -> float:
    """Compute the next backoff delay, capped at ``interval_seconds``.

    Args:
        retry_count: Number of retries already attempted (0 before first retry).
        retry_cfg: Parsed retry policy, or ``None`` for no backoff.
        interval_seconds: The task's normal interval — used as the backoff ceiling.

    Returns:
        Delay in seconds.  Never exceeds ``interval_seconds``.
    """
    if retry_cfg is None:
        # No retry config → wait at least 1 s then retry immediately
        return min(1.0, interval_seconds)

    base = retry_cfg.base
    strategy = retry_cfg.strategy

    if strategy == "exponential":
        delay = base * (2 ** retry_count)
    elif strategy == "multiplier":
        factor = retry_cfg.factor if retry_cfg.factor is not None else 1.5
        delay = base * (factor ** retry_count)
    else:  # "fixed"
        delay = base

    return min(delay, interval_seconds)
