# ADR-0007: Managed Tasks Design Decisions

**Date:** 2025-01-01  
**Status:** Accepted  
**Superseded by:** —

---

## Context

v0.9 introduces a periodic task scheduler (B09-S6/S7/S8). Several design questions arose during implementation that had non-obvious tradeoffs. This ADR records each decision and its rationale.

## Decision

### 1. Tasks are registered as ordinary functions

Tasks use `@function(task={...})` — the same decorator and same registry as all other Brimley functions. This means:

- A task is **discoverable** via the existing `Scanner` without a separate scan path.
- A task is **dispatchable** via `invoke <fn>` for ad-hoc invocation and testing, without special tooling.
- A task is **injectable** with DI-resolved arguments like any other function, so dependencies are described in the function signature rather than scheduler configuration.

The alternative (a separate `@task` decorator or a separate YAML section) would have introduced a second registry, a second dispatch path, and a second discovery mechanism for functionally equivalent behavior.

### 2. The scheduler enforces the overlap guard; manual invocation does not

`TaskScheduler` skips a scheduled run if the previous run has not completed (`RUNNING` state). This guard exists to prevent runaway backlog buildup when a task's runtime exceeds its interval.

Manual invocation via `brimley invoke <fn>` or an MCP tool call bypasses this guard intentionally. The guard is a scheduling concern, not a correctness constraint on the function itself. Blocking manual invocation behind the overlap guard would make ad-hoc triggering (for debugging or backfill) unexpectedly fail, with no clear indication that the scheduler state was the cause.

### 3. Shutdown ordering: tasks → @on_shutdown hooks → singletons

`BrimleyContainer.shutdown()` stops the `TaskScheduler` first, then runs `@on_shutdown` hooks, then disposes singletons. This ordering ensures:

1. No task run starts after shutdown begins.
2. `@on_shutdown` hooks execute with all singletons (databases, HTTP clients, caches) still alive.
3. Singletons are released only after all other cleanup is complete.

Reversing any pair in this order creates a window during which a scheduled task or hook could attempt to use an already-disposed resource.

### 4. Thirty-second global grace period for in-flight tasks

`TaskScheduler.stop()` sends a stop signal and waits up to 30 seconds for in-flight tasks to complete before forcing shutdown. The 30-second value was chosen as a reasonable upper bound for typical background tasks (reconciliation, cache warming, metric flush).

Per-task configurable grace periods are deferred to a future milestone (WL-004). The global value is sufficient for v0.9 and avoids the complexity of per-task shutdown tracking in the initial implementation.

### 5. Scheduling metadata is immutable across hot-reload

When source files are hot-reloaded (via `PartitionedReloadEngine`), the scheduler continues running with its original schedule. The function body is updated (new code executes on the next run), but interval, retries, and other `TaskConfig` fields are **not** re-read from the reloaded metadata.

Rationale: the scheduler's internal state (next-run time, failure count, retry countdown) is tied to the original `TaskConfig`. Silently updating these values mid-run would cause split-brain between the scheduler's expectations and the registered configuration — for example, resetting a retry countdown unexpectedly or altering the next-run calculation partway through a sequence.

A warning diagnostic (`WARN_TASK_SCHEDULE_CHANGED` or `WARN_NEW_TASK_FUNCTION`) is emitted when reloaded metadata diverges from the running schedule. A restart is required to apply schedule changes.

## Consequences

- Tasks share the function registry, discovery, and dispatch infrastructure with no duplication.
- Manual `invoke` always runs the function without scheduler-state side-effects.
- Shutdown is deterministic and resource-safe in all three runtime modes.
- The 30-second grace period may need tuning for workloads with long-running tasks (tracked as WL-004).
- Developers must restart `brimley repl` or `brimley mcp-serve` to change a task's schedule; editing only the function body is sufficient for logic changes.
