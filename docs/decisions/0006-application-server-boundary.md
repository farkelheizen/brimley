# ADR-0006: Application Server Boundary

**Date:** 2025-01-01  
**Status:** Accepted  
**Superseded by:** —

---

## Context

Before v0.9, Brimley supported an "embedded" deployment model in which a host application could instantiate `BrimleyRuntimeController` directly and embed Brimley as an in-process library component. Two problems surfaced that made this model unworkable at scale:

1. **Event loop contention.** The embedded model required Brimley to share the host application's asyncio event loop. When TaskScheduler was designed for v0.9, it became clear that a managed task scheduler requires sole ownership of its event loop to avoid contention, unpredictable scheduling jitter, and deadlocks caused by nested event loops. Running Brimley inside another framework's loop (FastAPI, Django async, etc.) makes this guarantee impossible to provide.

2. **Lifecycle ambiguity.** The embedded model placed responsibility for startup, shutdown, and error recovery on the host application. `BrimleyRuntimeController`'s lifecycle (scan → startup → reload → shutdown) had no reliable home: host frameworks had their own startup sequences that would race with or pre-empt Brimley's `@on_startup` hooks, and shutdown ordering (tasks → hooks → singletons) could not be enforced across the process boundary.

These constraints were documented implicitly in the three-phase shutdown design (B09-S9) and the TaskScheduler daemon thread model (B09-S6/S7/S8).

## Decision

**Brimley is an application server, not an embeddable library.**

The three supported runtime modes are:

| Mode | Command | Use case |
|------|---------|----------|
| `repl` | `brimley repl` | Interactive development and testing |
| `mcp-serve` | `brimley mcp-serve` | Production MCP server |
| `invoke` | `brimley invoke <fn>` | One-shot scripted invocation |

`BrimleyRuntimeController` is removed from the public API (from `__all__` in `src/brimley/__init__.py`). It remains available internally for the auto-reload watcher path but is no longer a supported integration point.

Applications that previously embedded Brimley in-process must migrate to an MCP-based sidecar model: run `brimley mcp-serve` as a separate process and connect to it via the MCP protocol. This is the recommended integration pattern from v0.9 onward.

## Consequences

**Positive:**
- TaskScheduler owns its event loop entirely, enabling deterministic scheduling behavior.
- Three-phase shutdown (tasks → @on_shutdown hooks → singletons) can be enforced in all modes.
- The public API surface is reduced and the supported integration patterns are explicit.
- `brimley mcp-serve --transport stdio` enables zero-network-overhead integration with MCP hosts.

**Trade-offs:**
- Embedding users must migrate to the MCP sidecar model or `invoke` CLI integration. This is a breaking change for any code that constructed `BrimleyRuntimeController` directly.
- The embedded deployments documentation (`brimley-embedded-deployments-and-port-management.md`) is archived.
- Out-of-process communication via MCP adds a serialization round-trip that in-process embedding avoided.
