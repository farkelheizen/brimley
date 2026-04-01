"""Runtime orchestration contracts and components."""

from brimley.runtime.controller import BrimleyRuntimeController, ReloadLifecycleEvent
from brimley.runtime.daemon import (
	ReplClientMetadata,
	acquire_repl_client_slot,
	DaemonMetadata,
	DaemonProbeResult,
	DaemonState,
	daemon_metadata_path,
	is_process_alive,
	probe_daemon_state,
	release_repl_client_slot,
	repl_client_metadata_path,
	recover_stale_daemon_metadata,
	shutdown_daemon_lifecycle,
	write_daemon_metadata,
)

# BrimleyRuntimeController is intentionally not in __all__. It is an internal
# implementation detail used by the CLI. Embedding support was removed in v0.9.
# Supported modes: repl, mcp-serve, invoke.

__all__ = [
	"DaemonMetadata",
	"DaemonProbeResult",
	"DaemonState",
	"ReplClientMetadata",
	"acquire_repl_client_slot",
	"daemon_metadata_path",
	"is_process_alive",
	"probe_daemon_state",
	"release_repl_client_slot",
	"repl_client_metadata_path",
	"recover_stale_daemon_metadata",
	"shutdown_daemon_lifecycle",
	"write_daemon_metadata",
]
