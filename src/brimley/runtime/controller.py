from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from brimley.config.loader import load_config
from brimley.core.context import BrimleyContext
from brimley.discovery.scanner import BrimleyScanResult, Scanner
from brimley.runtime.polling_watcher import PollingWatcher
from brimley.runtime.reload_contracts import ReloadCommandResult, ReloadCommandStatus
from brimley.runtime.reload_engine import PartitionedReloadEngine


@dataclass(frozen=True)
class ReloadLifecycleEvent:
    """Host-facing reload lifecycle event payload."""

    result: ReloadCommandResult


class BrimleyRuntimeController:
    """Host-agnostic runtime controller for non-REPL auto-reload integration."""

    def __init__(
        self,
        root_dir: Path,
        on_reload_success: Optional[Callable[[ReloadLifecycleEvent], None]] = None,
        on_reload_failure: Optional[Callable[[ReloadLifecycleEvent], None]] = None,
        mcp_refresh: Optional[Callable[[], object | None]] = None,
    ) -> None:
        self.root_dir = root_dir
        self.on_reload_success = on_reload_success
        self.on_reload_failure = on_reload_failure
        self.mcp_refresh = mcp_refresh

        config_data = load_config(self.root_dir / "brimley.yaml")
        self.context = BrimleyContext(config_dict=config_data)
        self.context.app["root_dir"] = str(self.root_dir.expanduser().resolve())

        self.reload_engine = PartitionedReloadEngine()
        self.auto_reload_watcher: Optional[PollingWatcher] = None
        self.auto_reload_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def load_initial(self) -> ReloadCommandResult:
        """Load initial discovery state into the runtime context."""
        return self.run_reload_cycle()

    def run_reload_cycle(self) -> ReloadCommandResult:
        """Run one reload cycle using partitioned policy-based semantics."""
        scan_result = self._scan()
        application_result = self.reload_engine.apply_reload_with_policy(self.context, scan_result)

        status = (
            ReloadCommandStatus.FAILURE
            if application_result.blocked_domains
            else ReloadCommandStatus.SUCCESS
        )

        if status == ReloadCommandStatus.SUCCESS and self.mcp_refresh is not None:
            self.mcp_refresh()

        result = ReloadCommandResult(
            status=status,
            summary=application_result.summary,
            diagnostics=application_result.diagnostics,
        )

        event = ReloadLifecycleEvent(result=result)
        if result.status == ReloadCommandStatus.SUCCESS and self.on_reload_success is not None:
            self.on_reload_success(event)
        elif result.status == ReloadCommandStatus.FAILURE and self.on_reload_failure is not None:
            self.on_reload_failure(event)

        return result

    def start_auto_reload(self, background: bool = True) -> None:
        """Start watcher lifecycle for host-managed auto-reload."""
        if not self.context.auto_reload.enabled:
            return

        if self.auto_reload_watcher is not None:
            return

        self.auto_reload_watcher = PollingWatcher(
            root_dir=self.root_dir,
            interval_ms=self.context.auto_reload.interval_ms,
            debounce_ms=self.context.auto_reload.debounce_ms,
            include_patterns=self.context.auto_reload.include_patterns,
            exclude_patterns=self.context.auto_reload.exclude_patterns,
        )
        self.auto_reload_watcher.start()
        self._stop_event.clear()

        if background:
            self.auto_reload_thread = threading.Thread(target=self._watch_loop, daemon=True)
            self.auto_reload_thread.start()

    def stop_auto_reload(self) -> None:
        """Stop watcher lifecycle and background loop if active."""
        self._stop_event.set()

        if self.auto_reload_thread is not None and self.auto_reload_thread.is_alive():
            self.auto_reload_thread.join(timeout=1)

        if self.auto_reload_watcher is not None:
            self.auto_reload_watcher.stop()

        self.auto_reload_thread = None
        self.auto_reload_watcher = None

    def poll_once(self, now: float) -> ReloadCommandResult | None:
        """Run a single watcher poll cycle; returns reload result if cycle triggered."""
        if self.auto_reload_watcher is None:
            return None

        poll_result = self.auto_reload_watcher.poll(now=now)
        if not poll_result.should_reload:
            return None

        result = self.run_reload_cycle()
        self.auto_reload_watcher.complete_reload(success=result.status == ReloadCommandStatus.SUCCESS)
        return result

    def _watch_loop(self) -> None:
        if self.auto_reload_watcher is None:
            return

        interval_seconds = max(self.context.auto_reload.interval_ms / 1000.0, 0.05)
        while not self._stop_event.is_set():
            self.poll_once(now=time.monotonic())
            self._stop_event.wait(interval_seconds)

    def _scan(self) -> BrimleyScanResult:
        if not self.root_dir.exists():
            return BrimleyScanResult()

        scanner = Scanner(self.root_dir)
        return scanner.scan()
