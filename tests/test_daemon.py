import os

from brimley.runtime.daemon import (
    DaemonMetadata,
    DaemonState,
    daemon_metadata_path,
    probe_daemon_state,
    recover_stale_daemon_metadata,
    write_daemon_metadata,
)


def test_probe_daemon_state_absent_when_metadata_missing(tmp_path):
    probe = probe_daemon_state(tmp_path)

    assert probe.state == DaemonState.ABSENT
    assert probe.metadata is None
    assert "not found" in probe.reason.lower()


def test_probe_daemon_state_running_for_current_pid(tmp_path):
    metadata = DaemonMetadata(
        pid=os.getpid(),
        port=8123,
        started_at="2026-02-25T00:00:00Z",
    )
    write_daemon_metadata(tmp_path, metadata)

    probe = probe_daemon_state(tmp_path)

    assert probe.state == DaemonState.RUNNING
    assert probe.metadata is not None
    assert probe.metadata.pid == os.getpid()
    assert probe.metadata.port == 8123


def test_probe_daemon_state_invalid_metadata_marks_stale(tmp_path):
    metadata_file = daemon_metadata_path(tmp_path)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.write_text("{not-json}")

    probe = probe_daemon_state(tmp_path)

    assert probe.state == DaemonState.STALE
    assert probe.metadata is None
    assert "invalid" in probe.reason.lower()


def test_probe_daemon_state_dead_pid_marks_stale(tmp_path, monkeypatch):
    metadata = DaemonMetadata(
        pid=424242,
        port=8123,
        started_at="2026-02-25T00:00:00Z",
    )
    write_daemon_metadata(tmp_path, metadata)

    monkeypatch.setattr("brimley.runtime.daemon.is_process_alive", lambda pid: False)

    probe = probe_daemon_state(tmp_path)

    assert probe.state == DaemonState.STALE
    assert probe.metadata is not None
    assert "not alive" in probe.reason.lower()


def test_recover_stale_daemon_metadata_removes_stale_file(tmp_path, monkeypatch):
    metadata = DaemonMetadata(
        pid=424242,
        port=8123,
        started_at="2026-02-25T00:00:00Z",
    )
    metadata_file = write_daemon_metadata(tmp_path, metadata)

    monkeypatch.setattr("brimley.runtime.daemon.is_process_alive", lambda pid: False)

    recovered = recover_stale_daemon_metadata(tmp_path)

    assert recovered is True
    assert metadata_file.exists() is False


def test_recover_stale_daemon_metadata_is_noop_for_running(tmp_path):
    metadata = DaemonMetadata(
        pid=os.getpid(),
        port=8123,
        started_at="2026-02-25T00:00:00Z",
    )
    metadata_file = write_daemon_metadata(tmp_path, metadata)

    recovered = recover_stale_daemon_metadata(tmp_path)

    assert recovered is False
    assert metadata_file.exists() is True
