import os

from brimley.runtime.daemon import (
    DaemonMetadata,
    DaemonState,
    allocate_ephemeral_port,
    acquire_repl_client_slot,
    daemon_metadata_path,
    probe_daemon_state,
    release_repl_client_slot,
    repl_client_metadata_path,
    recover_stale_daemon_metadata,
    shutdown_daemon_lifecycle,
    wait_for_daemon_running,
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


def test_acquire_repl_client_slot_succeeds_when_slot_missing(tmp_path):
    acquired = acquire_repl_client_slot(tmp_path)

    assert acquired is True
    assert repl_client_metadata_path(tmp_path).exists() is True


def test_acquire_repl_client_slot_fails_when_active_pid_exists(tmp_path, monkeypatch):
    acquire_repl_client_slot(tmp_path)
    monkeypatch.setattr("brimley.runtime.daemon.is_process_alive", lambda pid: True)

    acquired = acquire_repl_client_slot(tmp_path)

    assert acquired is False


def test_release_repl_client_slot_removes_file(tmp_path):
    acquire_repl_client_slot(tmp_path)
    metadata_file = repl_client_metadata_path(tmp_path)

    release_repl_client_slot(tmp_path)

    assert metadata_file.exists() is False


def test_shutdown_daemon_lifecycle_removes_daemon_and_client_metadata(tmp_path):
    daemon_metadata = DaemonMetadata(
        pid=os.getpid(),
        port=8123,
        started_at="2026-02-25T00:00:00Z",
    )
    daemon_file = write_daemon_metadata(tmp_path, daemon_metadata)
    acquire_repl_client_slot(tmp_path)
    client_file = repl_client_metadata_path(tmp_path)

    removed = shutdown_daemon_lifecycle(tmp_path)

    assert removed is True
    assert daemon_file.exists() is False
    assert client_file.exists() is False


def test_allocate_ephemeral_port_returns_valid_port():
    port = allocate_ephemeral_port()

    assert isinstance(port, int)
    assert 1 <= port <= 65535


def test_wait_for_daemon_running_returns_running_probe(tmp_path):
    metadata = DaemonMetadata(
        pid=os.getpid(),
        port=8123,
        started_at="2026-02-25T00:00:00Z",
    )
    write_daemon_metadata(tmp_path, metadata)

    probe = wait_for_daemon_running(tmp_path, expected_pid=os.getpid(), timeout_seconds=0.2, poll_interval_seconds=0.01)

    assert probe.state == DaemonState.RUNNING
    assert probe.metadata is not None
    assert probe.metadata.pid == os.getpid()
