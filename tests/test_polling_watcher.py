from pathlib import Path

from brimley.runtime.polling_watcher import PollingWatcher
from brimley.runtime.reload_contracts import WatcherState


def test_polling_watcher_tracks_files_with_include_exclude_patterns(tmp_path: Path):
    (tmp_path / "a.py").write_text("print('a')")
    (tmp_path / "b.sql").write_text("select 1")
    (tmp_path / "c.txt").write_text("ignore")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "skip.py").write_text("print('skip')")

    watcher = PollingWatcher(
        root_dir=tmp_path,
        include_patterns=["*.py", "*.sql"],
        exclude_patterns=[".venv/*"],
    )

    watcher.start()

    assert watcher.tracked_paths() == {"a.py", "b.sql"}


def test_polling_watcher_debounces_changes_until_window_elapses(tmp_path: Path):
    watcher = PollingWatcher(root_dir=tmp_path, debounce_ms=200)
    watcher.start()

    (tmp_path / "hello.py").write_text("print('v1')")

    first_poll = watcher.poll(now=0.10)
    assert first_poll.should_reload is False
    assert first_poll.changed_paths == []
    assert watcher.state == WatcherState.DEBOUNCING

    second_poll = watcher.poll(now=0.25)
    assert second_poll.should_reload is False

    final_poll = watcher.poll(now=0.35)
    assert final_poll.should_reload is True
    assert final_poll.changed_paths == ["hello.py"]
    assert watcher.state == WatcherState.RELOADING

    watcher.complete_reload(success=True)
    assert watcher.state == WatcherState.WATCHING


def test_polling_watcher_detects_deleted_files(tmp_path: Path):
    watched_file = tmp_path / "gone.py"
    watched_file.write_text("print('x')")

    watcher = PollingWatcher(root_dir=tmp_path, debounce_ms=100)
    watcher.start()

    watched_file.unlink()

    pending = watcher.poll(now=1.0)
    assert pending.should_reload is False

    ready = watcher.poll(now=1.2)
    assert ready.should_reload is True
    assert ready.changed_paths == ["gone.py"]
