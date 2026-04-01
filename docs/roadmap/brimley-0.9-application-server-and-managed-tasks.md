# Brimley 0.9: Application Server Boundary & Managed Tasks (@task)

> **Predecessor:** [0.8 Dependency Injection & Managed Objects](brimley-0.8-dependency-injection-and-managed-objects.md) — Managed Tasks build directly on the DI container, lifecycle hooks, and the AST scanning infrastructure shipped in v0.8.

## Overview

Managed Tasks allow developers to define autonomous, periodic background coroutines. A task is the "heartbeat" of a Brimley deployment — enabling reconciliation, polling, and self-healing logic that runs without requiring external triggers.

**A task is a Brimley Python function with scheduling metadata.** Tasks are not a separate artifact type — they are registered in the same `Registry[BrimleyFunction]`, discovered by the same `Scanner`, and executed through the same `Dispatcher.run()` path as any other Python function. The `TaskScheduler` simply queries the registry at startup for functions that carry a `task` configuration and manages their periodic execution.

This design means tasks are immediately testable via `brimley invoke`, callable from the REPL, and benefit from the full DI resolution path (`Depends()`, request-scoped providers, `BrimleyContext`) with no special infrastructure.

### Architectural Assumption: Application Server Boundary

As of this milestone, **Brimley is an application server.** It always owns its own process and event loop. Embedding Brimley as a library inside another Python application (e.g., importing `BrimleyRuntimeController` into a FastAPI app) is no longer a supported deployment model. This simplifies the `TaskScheduler` design significantly: the scheduler does not need to account for a foreign event loop or shared process ownership.

**Tasks are only active in long-running modes** (`repl`, `mcp-serve`). In `invoke` mode (one-shot function execution), the tasks subsystem is not started — the startup sequence skips `TaskScheduler.start()` entirely. This is the correct behavior: `invoke` executes a single function and exits, so background heartbeats would be pointless and could delay shutdown.

### Why v0.9?

Removing embedding support is a breaking change to Brimley's public API surface (e.g., `BrimleyRuntimeController` as a library entry point). That warrants a minor version bump rather than a patch release. Managed Tasks are bundled into the same release because they depend directly on the application server boundary — the `TaskScheduler` design is dramatically simpler when Brimley owns its process. This release has no structural dependency on v0.10 (Mocking) or later milestones, and it relies exclusively on machinery already shipped in v0.8: `BrimleyContainer`, `@on_startup`/`@on_shutdown` hooks, AST-based scanning, and request-scoped DI.

## 1. The Developer API

A task is declared using the standard `@function` decorator with an additional `task` parameter that supplies scheduling metadata. This makes it explicit that a task **is** a function.

```python
from brimley import function, BrimleyContext

@function(
    name="github_reconciler",
    task={"interval": "5m", "immediate": True, "retries": 5, "retry_interval": "10s exponential"},
)
async def poll_github_prs(ctx: BrimleyContext):
    """
    Checks for PRs created by the cloud swarm and updates local state.
    """
    # Call a brimley cli tool: gh pr list --label 'brimley-swarm' --json url,state
    # Call a brimley sql function: UPDATE tasks SET status = 'DONE' WHERE pr_url IN :urls
    # High-level logic using the DI-injected context
```

### Task Parameters (the `task` dict)

| Key              | Type   | Default   | Description                                                           |
|------------------|--------|-----------|-----------------------------------------------------------------------|
| `interval`       | `str`  | required  | Human-readable duration string (e.g., `"30s"`, `"5m"`, `"1h 30m"`). Minimum 1 second. |
| `immediate`      | `bool` | `False`   | If `True`, execute the first iteration immediately at startup.        |
| `retries`        | `int`  | `None` (unlimited) | Maximum number of consecutive retries before giving up. When exhausted, the task stops retrying until the next scheduled interval. If omitted, retries are unlimited (backoff continues indefinitely, capped at the task's own `interval`). |
| `retry_interval` | `str`  | `"1s exponential"` | Controls the delay between retries after a failure. Accepts three formats (see [Retry Interval Formats](#retry-interval-formats) below). |

The function's `name` (from `@function`) is the task's identity — no separate task name is needed.

### 1.1 MCP Prohibition

**A function with a `task` configuration must not have an `mcpType` set.** Task functions are system-internal background logic; exposing them to an LLM as tools, resources, or prompts is a security risk (autonomous reconciliation logic should not be LLM-callable).

If the `Scanner` detects a function with both `task` and `mcpType`, the function is **skipped entirely** — it is not registered in the function registry. A warning is emitted to the log:

```
[Scanner] Skipping 'github_reconciler': task functions cannot be MCP objects. Remove mcpType or task configuration.
```

This is a soft failure (skip + warn), not a hard abort. The rest of the server starts normally.

### 1.2 Signature Constraint

Task functions must accept only `BrimleyContext` and DI-injected `Depends()` parameters. They must not declare positional arguments that would need to be supplied by an LLM or user input, because the `TaskScheduler` cannot provide them on a timer.

The `Scanner` validates this at AST phase. If a task function declares non-injectable parameters (e.g., `username: str`), it is skipped with a warning:

```
[Scanner] Skipping 'my_task': task functions may only accept BrimleyContext and Depends() parameters.
```

### 1.3 Observability Distinction

Although tasks live in the same registry as other functions, they are distinguishable via the presence of `task` metadata on the `BrimleyFunction` model. In the DuckDB logs (v0.12), this allows clear separation between "System Logic" (functions with `task` metadata) and "Agent Logic" (functions without).

## 2. Lifecycle & The "Immutable Schedule" Rule

A task function's **logic** can be hot-reloaded like any other Python function. However, its **scheduling metadata** (`interval`, `immediate`, `retries`, `retry_interval`) is immutable at runtime. To ensure state integrity and prevent race conditions in background loops, Brimley enforces the following lifecycle:

1. **Discovery:** The `Scanner` identifies functions with a `task` configuration during the initial boot. They are registered in the standard `Registry[BrimleyFunction]` with their scheduling metadata attached.

2. **Hot-Reload Behavior (RE-SCAN):**
    - **Function logic changes:** If the Python function body is modified, the `PartitionedReloadEngine` reloads it normally (same as any Python function). The next scheduled iteration will execute the updated logic.
    - **New task functions:** If a new function with `task` metadata is detected during a re-scan, the scheduling is **ignored** — it will not be started until restart.
    - **Scheduling metadata changes:** If an existing task function's `interval`, `immediate`, `retries`, or `retry_interval` values change, the changes are **not applied** to the running schedule.
    - **Notification:** The REPL/Logs will emit a warning: `[Hot-Reload] Task scheduling changes detected. Restart Brimley to apply.`

3. **Activation:** The `TaskScheduler` launches scheduled iterations only once the server is "Ready" (after all `@on_startup` hooks complete and `BrimleyContainer.startup()` finishes). In `invoke` mode, this step is skipped entirely — the `TaskScheduler` is never started.

4. **Manual Invocation:** A task function can always be called manually via `brimley invoke <name>` or from the REPL, regardless of whether the `TaskScheduler` is running. Manual invocation executes the function once through `Dispatcher.run()` — no scheduling, no overlap guard. The scheduler's overlap prevention is internal to the `TaskScheduler` loop and does not affect manual invocation.

5. **Shutdown:** The shutdown sequence uses a three-phase ordering to ensure tasks are cancelled before shared resources are released:
    1. `TaskScheduler.stop()` — sends cancellation to all running task coroutines, awaits up to a 30-second grace period, then hard-cancels (`task.cancel()`) any remaining with a WARNING-level log entry.
    2. `BrimleyContainer._run_shutdown_hooks()` — existing `@on_shutdown` hooks run in reverse declaration order. At this point no task coroutines are running.
    3. `BrimleyContainer._teardown_singletons()` — existing singleton teardown.

    This ordering is critical because tasks may depend on singletons (e.g., a DB pool). The 30-second grace period is a global default; per-task `shutdown_timeout` is deferred to the wish list ([WL-004](brimley-wish-list.md#wl-004--per-task-shutdown_timeout)). In `invoke` mode, the scheduler was never started, so step 1 is a no-op.

## 3. The "C2" Coordination Pattern

A Managed Task is the primary way to implement a **Reconciler**.

- **State-Awareness:** Because tasks receive a `BrimleyContext`, they have full access to the project's database connections and registries.

- **Decoupled Execution:** Tasks run in the background, meaning they don't block the `stdio` pipe used by the LLM. An agent can call a tool while multiple tasks are running concurrently.

## 4. Error Handling & Resilience

Tasks must be more resilient than standard functions because they have no "User" to report an error to.

- **Isolation:** An exception in a task must not crash the Brimley server or other tasks.

- **Logging:** All task failures are logged with a unique `correlation_id` to the `logs.jsonl` sink.

### Retry Policy

When a task iteration fails (unhandled exception), the `TaskScheduler` retries according to the `retry_interval` and `retries` parameters.

- **Backoff ceiling:** Retry delays are always capped at `min(computed_delay, interval)`. A task with `interval="5m"` never waits longer than 5 minutes between retries.
- **Reset:** A single successful iteration resets the retry counter and backoff delay to zero.
- **Exhaustion:** If `retries` is set and the counter is exhausted, the task stops retrying and waits for the next normal scheduled interval. This is logged as a WARNING.
- **Unlimited retries:** If `retries` is omitted, backoff continues indefinitely (capped at `interval`) until the task succeeds.

#### Retry Interval Formats

The `retry_interval` parameter accepts three string formats:

| Format | Example | Behavior |
|---|---|---|
| `<duration> exponential` | `"10s exponential"` or `"10s ex"` | Base delay doubles each retry: 10s, 20s, 40s, 80s, ... capped at `interval`. |
| `<duration> x<multiplier>` | `"10s x1.5"` | Base delay multiplied by the given factor each retry: 10s, 15s, 22.5s, 33.75s, ... capped at `interval`. |
| `<duration>` (fixed) | `"10s"` | Constant delay between retries: 10s, 10s, 10s, ... |

The `<duration>` component uses the same human-time parser as `interval` (e.g., `"1m 30s"`, `"500ms"`).

If `retry_interval` is omitted entirely, the default is `"1s exponential"` (1s, 2s, 4s, 8s, 16s, ... capped at `interval`).

> **Telemetry & Metrics** — Deferred to [WL-002](brimley-wish-list.md#wl-002--telemetry-configuration-block-brimleyyaml). For v0.9, task metrics (`last_run_time`, `success_count`, `failure_count`, `avg_duration`) are emitted as structured log lines. A unified telemetry backend (`telemetry:` config block, DuckDB storage, introspection queries) will land in v0.12.

## 5. Implementation Design Items

- **`TaskScheduler` Service:** A new DI-managed singleton that runs on a **dedicated daemon thread with its own `asyncio` event loop**. This keeps the architecture uniform across REPL and `mcp-serve` modes without coupling to FastMCP internals, consistent with the existing patterns for the auto-reload watcher and embedded MCP server thread. At startup, it queries `Registry[BrimleyFunction]` for functions with `task` metadata and starts their periodic execution. The scheduler is instantiated but not started in `invoke` mode. All `immediate=True` tasks launch concurrently once the server is "Ready" (after `@on_startup` hooks) — there is no guaranteed ordering among them.

- **`task` Parameter on `@function`:** Extend the `@function` decorator to accept an optional `task` dict. The Scanner's AST phase extracts `task` kwargs and attaches them to the `PythonFunction` model as scheduling metadata.

- **MCP + Task Conflict Detection:** During the Scanner's validation phase, any function that declares both `task` and `mcpType` is quarantined (skipped) with a warning log entry. The function is not registered.

- **Signature Validation:** During the Scanner's validation phase, task functions are checked to ensure they only accept `BrimleyContext` and `Depends()` parameters. Functions with non-injectable positional arguments are quarantined.

- **`async` Validation:** The Scanner (AST phase) enforces that task functions are `async def`. If `task` is applied to a synchronous function (`def`), the function is quarantined (skipped) with a warning. This is a single `ast.AsyncFunctionDef` vs `ast.FunctionDef` node-type check.

- **Human-Time Parser:** A utility to convert strings like `"1h 30m"` into total seconds. Also handles the `retry_interval` format (e.g., `"10s exponential"`, `"10s x1.5"`).

- **Interval Minimum Bound:** The human-time parser rejects `interval` values that parse to less than 1 second. This is a scan-time validation (skip + warn), consistent with the other quarantine rules.

- **Overlap Prevention:** A mandatory guard — internal to the `TaskScheduler` loop — to ensure a task doesn't start its next scheduled iteration if the previous one is still running. Manual invocations via `brimley invoke` or the REPL are **not** subject to this guard — they execute through `Dispatcher.run()` independently.

- **Overlap Diagnostic Warning:** The `TaskScheduler` tracks a `consecutive_skip_count` per task. After 3 consecutive scheduler-initiated skips, emit a WARNING: `[TaskScheduler] Task 'X' has been running longer than its interval for 3 consecutive iterations. Consider increasing the interval or optimizing the task logic.` The counter resets when an iteration completes before the next scheduled start. Manual invocations do not affect this counter.

- **`/tasks` REPL Admin Command:** Ship a `/tasks` command in v0.9 that lists all functions with task metadata and their current scheduling state: task name, interval, state (`running`, `waiting`, `backoff`), last run time, consecutive failure count, and next scheduled run. This is a read-only introspection command.

- **Hot-Reload Warning for Scheduling Changes:** The `PartitionedReloadEngine` detects scheduling metadata changes during re-scan and emits: `[Hot-Reload] Task scheduling changes detected for 'X'. Restart Brimley to apply.` Only function logic changes are applied at runtime; scheduling metadata remains immutable until restart.

- **Three-Phase Shutdown:** Modify `BrimleyContainer.shutdown()` to insert task cancellation before the existing hooks and teardown steps (see Section 2, step 5). Backwards-compatible for projects without tasks (step 1 is a no-op).

- **Security Documentation:** As part of v0.9 documentation, include a security note stating that task functions run with the same trust boundary as `@function` and `@provider` — full `BrimleyContext` access, full DI container access. The trust model is: the developer who deploys the project trusts all code in the project directory.

- **`mcp-serve` stdio Transport Support:** Wire the existing `mcp.transport` config value (`"sse"` or `"stdio"`) through to `mcp_server.run()` in the `mcp-serve` command. When `transport` is `"stdio"`, FastMCP uses stdin/stdout — no HTTP server is started, and `--host`/`--port` flags are ignored. This is how most MCP clients (Claude Desktop, VS Code) prefer to connect. The REPL embedded MCP server always uses SSE regardless of config, because stdio would conflict with the interactive terminal. Add a `--transport` CLI flag to `mcp-serve` as an override.

- **`brimley build` Documentation Update:** The `brimley build` command currently generates asset shims but is not ready for production use. As part of v0.9, update the CLI help text, the command's docstring, and any references in `docs/` to clearly mark `brimley build` as **experimental / not ready for use**. This prevents confusion now that the application server boundary reframes how `build` will eventually work (see [WL-003](brimley-wish-list.md#wl-003--single-file-distribution-brimley-build---bundle)).

## 6. Documentation & ADR Requirements

The following documentation updates must be completed as part of the v0.9 release. These are not optional follow-ups — they are deliverables gated alongside the implementation.

### ADR: Application Server Boundary

Create **ADR-0006: Application Server Boundary** in `docs/decisions/`. This ADR documents the decision to remove embedding support and establish Brimley as an application server that always owns its process and event loop.

Key points to cover:
- **Context:** The embedding model (`BrimleyRuntimeController` as a library inside FastAPI, Django, etc.) creates event loop contention, lifecycle ambiguity, and complicates the `TaskScheduler` design.
- **Decision:** Brimley is an application server. `BrimleyRuntimeController` is removed from the public API. The three supported modes are `repl`, `mcp-serve`, and `invoke`.
- **Consequences:** Embedding users must migrate to MCP-based integration (Brimley as a sidecar process). `brimley-embedded-deployments-and-port-management.md` is archived. The `TaskScheduler` can assume sole ownership of its event loop.

### ADR: Managed Tasks Design Decisions

Create **ADR-0007: Managed Tasks Design Decisions** in `docs/decisions/`. This ADR captures the key design choices made during v0.9 planning that are not self-evident from the spec alone.

Key points to cover:
- **Tasks as functions:** Tasks use `@function(task={...})` rather than a separate `@task` decorator. Rationale: single registry, single dispatch path, testable via `brimley invoke`.
- **Scheduler-only overlap guard:** Manual invocation bypasses the overlap guard. Rationale: developer control, REPL ergonomics.
- **Three-phase shutdown ordering:** Tasks cancelled before `@on_shutdown` hooks, hooks before singleton teardown. Rationale: tasks depend on singletons.
- **30-second global grace period:** Global default, hard cancellation after expiry. Per-task `shutdown_timeout` deferred to wish list.
- **Immutable scheduling metadata:** Hot-reload applies to function logic only; `interval`, `immediate`, `retries`, and `retry_interval` require a restart.

### Documentation Updates

| Document | Update Required |
|---|---|
| `docs/brimley-high-level-design.md` | Add Managed Tasks as a subsystem. Update architecture diagram to show `TaskScheduler`. Reframe Brimley as an application server (remove embedding references). |
| `docs/brimley-python-functions.md` | Add `task` parameter documentation to the `@function` decorator reference. Include the task parameters table, retry interval formats, and scanner quarantine rules. |
| `docs/brimley-functions.md` | Add a "Task Functions" subsection explaining that tasks are Python functions with scheduling metadata, not a separate function type. |
| `docs/brimley-repl-admin-commands.md` | Document the new `/tasks` command: output format, columns, and states. |
| `docs/brimley-configuration.md` | No `task:` block in `brimley.yaml` — tasks are configured per-function via the decorator. Add a note clarifying this. |
| `docs/brimley-embedded-deployments-and-port-management.md` | Archive or add a deprecation header: "This deployment model is removed as of v0.9. See [ADR-0006](../decisions/0006-application-server-boundary.md)." |
| `docs/brimley-discovery-and-loader-specification.md` | Document the new Scanner quarantine rules: MCP prohibition, signature constraint, `async` validation, interval minimum. |
| `docs/security/` | Add a security note on task trust boundaries: tasks run with full `BrimleyContext` access, same trust model as `@function` and `@provider`. |
| `README.md` | Update project description to reflect application server model. Remove any references to embedding Brimley as a library. |

## 7. Roadmap Renumbering Plan

Inserting v0.9 shifts all subsequent milestones by one. The following changes must be applied before implementation begins.

### File Renames

| Current File | New File |
|---|---|
| `brimley-0.9-mocking-framework-and-mcp-interactivity.md` | `brimley-0.10-mocking-framework-and-mcp-interactivity.md` |
| `brimley-0.10-testing-framework.md` | `brimley-0.11-testing-framework.md` |
| `brimley-0.11-duckdb-introspection-and-repl-analytics.md` | `brimley-0.12-duckdb-introspection-and-repl-analytics.md` |
| `brimley-0.12-smart-caching-and-invalidation.md` | `brimley-0.13-smart-caching-and-invalidation.md` |
| `brimley-0.13-plugin-architecture-custom-function-types.md` | `brimley-0.14-plugin-architecture-custom-function-types.md` |
| `copilot-schema-reference-guide.md` | *(no rename — update content only)* |

> **Note:** v0.14 (Manifest & Schema Export) has no dedicated spec file. It is described inline in `index.md` and becomes v0.15.

### Content Updates: Roadmap Index (`docs/roadmap/index.md`)

- Insert new `## v0.9` entry for "Application Server Boundary & Managed Tasks" between v0.8 and the current v0.9.
- Renumber all subsequent version headers and file links: v0.9→v0.10, v0.10→v0.11, v0.11→v0.12, v0.12→v0.13, v0.13→v0.14, v0.14→v0.15.
- Update the "Path to v1.0" reference to `v0.12 core` → `v0.13 core`.

### Content Updates: Renumbered Spec Files

Each renamed file needs its H1 title and any self-referencing version numbers updated:

| File (new name) | Updates |
|---|---|
| `brimley-0.10-mocking-...md` | H1: 0.9→0.10. Body: "v0.9 spec"→"v0.10 spec", "DI (v0.8) precedes Mocking (v0.9)"→"(v0.10)", "v0.9 feature"→"v0.10 feature". |
| `brimley-0.11-testing-...md` | H1: 0.10→0.11. Body: "Brimley 0.10 provides"→"Brimley 0.11 provides". |
| `brimley-0.12-duckdb-...md` | H1: 0.11→0.12. Body: "Brimley 0.11 integrates"→"Brimley 0.12 integrates". |
| `brimley-0.13-smart-caching-...md` | H1: 0.12→0.13. Body: "Brimley 0.12 introduces"→"Brimley 0.13 introduces". |
| `brimley-0.14-plugin-...md` | H1: 0.13→0.14. Body: "v0.13 adds"→"v0.14 adds", "deferred...to v0.13"→"to v0.14". |
| `copilot-schema-reference-guide.md` | "v0.9 Manifest"→"v0.15 Manifest" (manifest was v0.14, now v0.15). |

### Content Updates: Cross-Referencing Spec Files (v0.7, v0.8)

These files reference future milestones that are now renumbered:

| File | References to Update |
|---|---|
| `brimley-0.8-dependency-injection-...md` | "Mocking — v0.9"→"v0.10", "v0.9 Mocking framework"→"v0.10", "v0.9 Mocking spec"→"v0.10". |
| `brimley-0.7-api-functions.md` | "v0.9 Mocking"→"v0.10 Mocking", "v0.13 plugin"→"v0.14 plugin". |
| `brimley-0.7-cli-functions.md` | "v0.9 Mocking"→"v0.10 Mocking", "v0.13"→"v0.14". |

### Content Updates: ADR Decision Files (`docs/decisions/`)

| File | References to Update |
|---|---|
| `0001-swap-di-and-mocking-order.md` | "0.9 Mocking"→"0.10 Mocking". |
| `0002-accelerate-api-cli-to-v0.7.md` | "v0.9 roadmap"→"v0.10 roadmap", "v0.9 spec"→"v0.10 spec", "v0.10–v0.12"→"v0.11–v0.13". |
| `0004-defer-plugin-architecture-to-v0.13.md` | "v0.13"→"v0.14" throughout, "v0.9 spec"→"v0.10 spec", version table rows updated. Consider renaming file to `0004-defer-plugin-architecture-to-v0.14.md`. |
| `0005-defer-manifest-to-v0.14.md` | "v0.14"→"v0.15" throughout, "v0.13"→"v0.14", version table rows updated. Consider renaming file to `0005-defer-manifest-to-v0.15.md`. |
| `README.md` | "v0.13"→"v0.14", "v0.14"→"v0.15". |

### Content Updates: Core Docs (`docs/`)

| File | References to Update |
|---|---|
| `brimley-api-functions.md` | "v0.9 Mocking"→"v0.10 Mocking". |
| `brimley-cli-functions.md` | "v0.9 Mocking"→"v0.10 Mocking". |
| `brimley-high-level-design.md` | "v0.9 Mocking integration seam"→"v0.10". |
| `brimley-embedded-deployments-and-port-management.md` | Archive or add deprecation header noting this deployment model is removed in v0.9. |
