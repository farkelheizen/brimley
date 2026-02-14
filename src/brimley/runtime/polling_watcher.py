from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Set

from brimley.runtime.reload_contracts import (
    WatcherEvent,
    WatcherState,
    transition_watcher_state,
)


@dataclass(frozen=True)
class WatcherPollResult:
    """Result from one watcher poll cycle."""

    should_reload: bool
    changed_paths: List[str]


class PollingWatcher:
    """Polling-based file watcher with include/exclude filters and debounce logic."""

    def __init__(
        self,
        root_dir: Path,
        interval_ms: int = 1000,
        debounce_ms: int = 300,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> None:
        self.root_dir = root_dir
        self.interval_ms = interval_ms
        self.debounce_ms = debounce_ms
        self.include_patterns = include_patterns or ["*.py", "*.sql", "*.md", "*.yaml"]
        self.exclude_patterns = exclude_patterns or []

        self.state: WatcherState = WatcherState.STOPPED
        self._snapshot: Dict[str, int] = {}
        self._pending_changes: Set[str] = set()
        self._last_change_at: Optional[float] = None

    def start(self) -> None:
        """Start watcher lifecycle and initialize file snapshot."""
        self.state = transition_watcher_state(self.state, WatcherEvent.START)
        self._snapshot = self._build_snapshot()

    def stop(self) -> None:
        """Stop watcher lifecycle."""
        self.state = transition_watcher_state(self.state, WatcherEvent.STOP)

    def complete_reload(self, success: bool) -> None:
        """Complete a reload cycle and transition back to watching state."""
        if self.state != WatcherState.RELOADING:
            return
        event = WatcherEvent.RELOAD_SUCCESS if success else WatcherEvent.RELOAD_FAILURE
        self.state = transition_watcher_state(self.state, event)

    def poll(self, now: float) -> WatcherPollResult:
        """Execute one poll cycle and return whether debounce window is ready to reload."""
        if self.state == WatcherState.STOPPED:
            raise RuntimeError("PollingWatcher is not started. Call start() before poll().")

        if self.state == WatcherState.RELOADING:
            return WatcherPollResult(should_reload=False, changed_paths=[])

        current_snapshot = self._build_snapshot()
        changed_paths = self._detect_changes(self._snapshot, current_snapshot)
        self._snapshot = current_snapshot

        if changed_paths:
            self._pending_changes.update(changed_paths)
            self._last_change_at = now
            self._enter_debounce_window()
            return WatcherPollResult(should_reload=False, changed_paths=[])

        if self.state == WatcherState.DEBOUNCING and self._last_change_at is not None:
            debounce_seconds = self.debounce_ms / 1000.0
            if (now - self._last_change_at) >= debounce_seconds:
                self.state = transition_watcher_state(self.state, WatcherEvent.DEBOUNCE_ELAPSED)
                paths = sorted(self._pending_changes)
                self._pending_changes.clear()
                self._last_change_at = None
                return WatcherPollResult(should_reload=True, changed_paths=paths)

        return WatcherPollResult(should_reload=False, changed_paths=[])

    def tracked_paths(self) -> Set[str]:
        """Return current tracked relative paths from the latest snapshot."""
        return set(self._snapshot.keys())

    def _enter_debounce_window(self) -> None:
        if self.state == WatcherState.WATCHING:
            self.state = transition_watcher_state(self.state, WatcherEvent.FILE_CHANGE)
            self.state = transition_watcher_state(self.state, WatcherEvent.DEBOUNCE_WINDOW_OPEN)
            return

        if self.state == WatcherState.DEBOUNCING:
            self.state = transition_watcher_state(self.state, WatcherEvent.FILE_CHANGE)
            self.state = transition_watcher_state(self.state, WatcherEvent.DEBOUNCE_WINDOW_OPEN)

    def _build_snapshot(self) -> Dict[str, int]:
        snapshot: Dict[str, int] = {}
        if not self.root_dir.exists():
            return snapshot

        for path in self.root_dir.rglob("*"):
            if not path.is_file():
                continue

            relative = path.relative_to(self.root_dir).as_posix()
            if not self._is_tracked_path(relative, path.name):
                continue

            snapshot[relative] = path.stat().st_mtime_ns

        return snapshot

    def _is_tracked_path(self, relative_path: str, filename: str) -> bool:
        included = any(
            fnmatch(relative_path, pattern) or fnmatch(filename, pattern)
            for pattern in self.include_patterns
        )
        if not included:
            return False

        excluded = any(
            fnmatch(relative_path, pattern) or fnmatch(filename, pattern)
            for pattern in self.exclude_patterns
        )
        return not excluded

    @staticmethod
    def _detect_changes(previous: Dict[str, int], current: Dict[str, int]) -> Set[str]:
        changes: Set[str] = set()

        previous_paths = set(previous.keys())
        current_paths = set(current.keys())

        for added in current_paths - previous_paths:
            changes.add(added)

        for removed in previous_paths - current_paths:
            changes.add(removed)

        for existing in previous_paths & current_paths:
            if previous[existing] != current[existing]:
                changes.add(existing)

        return changes
