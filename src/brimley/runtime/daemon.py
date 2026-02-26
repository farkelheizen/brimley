from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class DaemonState(str, Enum):
    """Classification of daemon metadata/liveness state."""

    ABSENT = "absent"
    RUNNING = "running"
    STALE = "stale"


class DaemonMetadata(BaseModel):
    """Persisted daemon liveness metadata."""

    pid: int = Field(gt=0)
    port: int = Field(ge=1, le=65535)
    started_at: str
    host: str = "127.0.0.1"


class DaemonProbeResult(BaseModel):
    """Result payload from probing daemon metadata/liveness."""

    state: DaemonState
    metadata: DaemonMetadata | None = None
    metadata_path: str
    reason: str


class ReplClientMetadata(BaseModel):
    """Persisted active REPL client metadata."""

    pid: int = Field(gt=0)
    attached_at: str


def daemon_metadata_path(root_dir: Path) -> Path:
    """Return the daemon metadata file path for a project root."""
    return root_dir / ".brimley" / "daemon.json"


def repl_client_metadata_path(root_dir: Path) -> Path:
    """Return the active REPL client metadata file path for a project root."""
    return root_dir / ".brimley" / "repl_client.json"


def write_daemon_metadata(root_dir: Path, metadata: DaemonMetadata) -> Path:
    """Persist daemon metadata for a project root."""
    metadata_file = daemon_metadata_path(root_dir)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    return metadata_file


def is_process_alive(pid: int) -> bool:
    """Return True when a process id appears to be alive on this host."""
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False

    return True


def probe_daemon_state(root_dir: Path) -> DaemonProbeResult:
    """Classify daemon state for a root as absent, running, or stale."""
    metadata_file = daemon_metadata_path(root_dir)
    if not metadata_file.exists():
        return DaemonProbeResult(
            state=DaemonState.ABSENT,
            metadata=None,
            metadata_path=str(metadata_file),
            reason="Daemon metadata file not found.",
        )

    try:
        payload = json.loads(metadata_file.read_text(encoding="utf-8"))
        metadata = DaemonMetadata.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return DaemonProbeResult(
            state=DaemonState.STALE,
            metadata=None,
            metadata_path=str(metadata_file),
            reason=f"Invalid daemon metadata payload: {exc}",
        )

    if not is_process_alive(metadata.pid):
        return DaemonProbeResult(
            state=DaemonState.STALE,
            metadata=metadata,
            metadata_path=str(metadata_file),
            reason=f"Daemon process pid={metadata.pid} is not alive.",
        )

    return DaemonProbeResult(
        state=DaemonState.RUNNING,
        metadata=metadata,
        metadata_path=str(metadata_file),
        reason="Daemon process is alive.",
    )


def recover_stale_daemon_metadata(root_dir: Path) -> bool:
    """Delete stale daemon metadata file when state is classified as stale."""
    probe = probe_daemon_state(root_dir)
    if probe.state != DaemonState.STALE:
        return False

    metadata_file = Path(probe.metadata_path)
    if metadata_file.exists():
        metadata_file.unlink()
    return True


def acquire_repl_client_slot(root_dir: Path) -> bool:
    """Acquire single-active-client slot; returns False when active client already exists."""
    metadata_file = repl_client_metadata_path(root_dir)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    if metadata_file.exists():
        try:
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
            existing = ReplClientMetadata.model_validate(payload)
            if is_process_alive(existing.pid):
                return False
        except (OSError, json.JSONDecodeError, ValidationError):
            pass

    metadata = ReplClientMetadata(pid=os.getpid(), attached_at="active")
    metadata_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    return True


def release_repl_client_slot(root_dir: Path) -> None:
    """Release active REPL client slot metadata if present."""
    metadata_file = repl_client_metadata_path(root_dir)
    if metadata_file.exists():
        metadata_file.unlink()


def shutdown_daemon_lifecycle(root_dir: Path) -> bool:
    """Remove daemon and active-client metadata and return whether anything was removed."""
    removed = False
    daemon_file = daemon_metadata_path(root_dir)
    client_file = repl_client_metadata_path(root_dir)

    if daemon_file.exists():
        daemon_file.unlink()
        removed = True

    if client_file.exists():
        client_file.unlink()
        removed = True

    return removed
