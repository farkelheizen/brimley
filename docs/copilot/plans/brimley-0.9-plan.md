# 20260328-brimley-0.9 Plan: Application Server Boundary & Managed Tasks

> Date: 3/28/2026
> Owner: Copilot
> Branch: `copilot/plan-b09` (integration branch; step branches merge here, final merge to `main`)
> Related docs: `docs/roadmap/brimley-0.9-application-server-and-managed-tasks.md`, `docs/roadmap/brimley-wish-list.md`, `docs/brimley-high-level-design.md`, `docs/brimley-python-functions.md`, `docs/brimley-functions.md`, `docs/brimley-discovery-and-loader-specification.md`, `docs/brimley-repl-admin-commands.md`, `docs/brimley-configuration.md`, `docs/brimley-cli-and-repl-harness.md`, `docs/brimley-context.md`

This file is intended as a working implementation plan.

## Problem Summary

Brimley 0.8 shipped Dependency Injection, managed singletons, lifecycle hooks, and request-scoped providers. However, Brimley still exposes `BrimleyRuntimeController` as a public API for embedding inside other Python applications (e.g., FastAPI). This embedding model creates event loop contention, lifecycle ambiguity, and complicates the design of any background task system. There is also no mechanism for declaring autonomous, periodic background coroutines — a critical need for reconciliation, polling, and self-healing logic in agent-oriented deployments.

The existing startup and shutdown sequences assume one-shot or interactive use. There is no `TaskScheduler`, no periodic execution loop, and no coordination between background work and the MCP/REPL interface layers. Additionally, the `mcp-serve` command hardcodes SSE transport, even though the config schema already supports `transport: "stdio"` — the preferred connection method for most MCP clients (Claude Desktop, VS Code).

## Goal

Establish Brimley as an application server that always owns its process and event loop, deliver a Managed Tasks subsystem (`@function(task={...})`) with scheduling, retry, and overlap prevention, wire stdio transport for `mcp-serve`, and complete all roadmap renumbering required by the v0.9 insertion.

## Scope

- In scope:
  - Remove embedding support: deprecate/remove `BrimleyRuntimeController` from the public API
  - `task` parameter on `@function` decorator with scheduling metadata (`interval`, `immediate`, `retries`, `retry_interval`)
  - `TaskScheduler` singleton service: dedicated daemon thread, own event loop, periodic execution
  - Scanner quarantine rules: MCP prohibition, signature constraint, async validation, interval minimum
  - Human-time parser utility (`"1h 30m"` → seconds, plus retry_interval format parsing)
  - Retry policy: exponential/multiplier/fixed backoff, ceiling, reset, exhaustion
  - Overlap prevention (scheduler-only) with diagnostic warning after 3 consecutive skips
  - Three-phase shutdown: TaskScheduler.stop() → @on_shutdown hooks → singleton teardown
  - `/tasks` REPL admin command
  - Hot-reload warning for scheduling metadata changes
  - `mcp-serve` stdio transport support with `--transport` CLI flag override
  - `brimley build` documentation: mark as experimental
  - ADR-0006 (Application Server Boundary) and ADR-0007 (Managed Tasks Design Decisions)
  - Documentation updates per Section 6 of the roadmap spec
  - Roadmap renumbering: file renames + content updates per Section 7
  - Security documentation for task trust boundaries
  - Version bump, CHANGELOG, doc scan gate

- Out of scope:
  - Per-task `shutdown_timeout` (WL-004)
  - `/task restart` admin command (WL-005)
  - Cron-style scheduling (WL-006)
  - Jitter / randomized delay (WL-007)
  - MCP server authentication (WL-008)
  - Telemetry backend / DuckDB metrics (v0.12)
  - Mocking framework (v0.10)
  - Testing framework (v0.11)

## Constraints / Requirements

- Treat `docs/roadmap/brimley-0.9-application-server-and-managed-tasks.md` as the source of truth for v0.9 behavior.
- **Application server boundary**: Brimley always owns its process and event loop. No embedding support.
- **Tasks are functions**: Tasks use `@function(task={...})`, not a separate `@task` decorator. Single registry, single dispatch path.
- **Zero-execution AST scan**: The `task` parameter must be detected via `ast.parse()` in the Scanner's AST phase, consistent with the existing two-phase scanning model.
- **Tasks active only in long-running modes**: `repl` and `mcp-serve` start the `TaskScheduler`. `invoke` mode skips it entirely.
- **Immutable scheduling metadata**: Hot-reload applies to function logic only. Scheduling metadata (`interval`, `immediate`, `retries`, `retry_interval`) requires a restart.
- **Scheduler-only overlap guard**: Manual invocation via `brimley invoke` or REPL bypasses overlap prevention.
- **Three-phase shutdown ordering**: TaskScheduler.stop() → @on_shutdown hooks → singleton teardown. 30-second global grace period.
- **Quarantine rules are soft failures**: Skip + warn. Do not abort the server for individual function violations.
- **stdio transport**: REPL embedded MCP server always uses SSE regardless of config (stdio conflicts with interactive terminal).
- Use Poetry commands for all validation/test execution.
- Preserve all existing v0.8 behavior and test coverage.

---

## Implementation Plan

| Step ID | Status | Goal | Planned Changes | Test Coverage |
|---|---|---|---|---|
| B09-S1 | Completed | Roadmap renumbering (file renames + content updates) | Rename spec files (0.9→0.10, 0.10→0.11, etc.), update H1 titles, cross-references in specs, ADRs, core docs, `index.md` | Manual verification of file renames and reference consistency |
| B09-S2 | Completed | Remove embedding support | Remove/deprecate `BrimleyRuntimeController` from public API; archive `brimley-embedded-deployments-and-port-management.md` | `tests/test_packaging_contract.py` (removed export); regression on existing tests |
| B09-S3 | Completed | Human-time parser utility | New `utils/time_parser.py`: parse `"1h 30m"`, `"500ms"`, `"30s"` → seconds; parse retry_interval formats (`"10s exponential"`, `"10s x1.5"`, `"10s"`) | `tests/test_time_parser.py` (valid durations, edge cases, retry formats, errors) |
| B09-S4 | Completed | Task metadata model and @function extension | Extend `@function` decorator to accept `task` dict; `TaskConfig` Pydantic model; `PythonFunction` / `BrimleyFunction` gains optional `task` field | `tests/test_di_models.py` or `tests/test_task_models.py` (model validation); `tests/test_decorators.py` (task parameter) |
| B09-S5 | Completed | Scanner AST extraction and quarantine rules | `python_parser.py`: extract `task` kwargs from `@function` AST; `scanner.py`: quarantine rules (MCP prohibition, signature constraint, async validation, interval minimum) | `tests/test_discovery.py` / `tests/test_task_discovery.py` (AST extraction, all 4 quarantine rules, valid task functions) |
| B09-S6 | Not Started | TaskScheduler core (daemon thread + event loop) | New `core/task_scheduler.py`: `TaskScheduler` class with `start()`, `stop()`, periodic execution loop, `immediate` handling | `tests/test_task_scheduler.py` (start/stop, periodic execution, immediate flag, not started in invoke mode) |
| B09-S7 | Not Started | Retry policy implementation | `TaskScheduler` retry logic: exponential/multiplier/fixed backoff, ceiling at `interval`, reset on success, exhaustion handling | `tests/test_task_scheduler.py` (retry formats, backoff ceiling, reset, exhaustion, unlimited retries) |
| B09-S8 | Not Started | Overlap prevention and diagnostic warning | `TaskScheduler` overlap guard: skip iteration if previous running; `consecutive_skip_count` tracking; 3-skip WARNING | `tests/test_task_scheduler.py` (overlap skip, diagnostic warning at 3 skips, counter reset, manual invoke bypasses guard) |
| B09-S9 | Not Started | Three-phase shutdown | Modify `BrimleyContainer.shutdown()`: insert `TaskScheduler.stop()` (30s grace → hard cancel) before hooks and teardown; no-op when no tasks | `tests/test_task_scheduler.py` (graceful stop, hard cancel after timeout); `tests/test_container.py` (three-phase ordering, backward compat) |
| B09-S10 | Not Started | Startup sequence integration | Wire `TaskScheduler` into boot path: instantiate after container ready, query registry for task functions, `start()` after `@on_startup` hooks (only in repl/mcp-serve modes) | `tests/test_startup.py` (task scheduler started in repl/mcp-serve, skipped in invoke, start after hooks) |
| B09-S11 | Not Started | `/tasks` REPL admin command | New REPL command showing task name, interval, state (running/waiting/backoff), last run, failure count, next scheduled run | `tests/test_repl_commands.py` or `tests/test_tasks_command.py` (output format, states, empty list) |
| B09-S12 | Not Started | Hot-reload warning for scheduling changes | `PartitionedReloadEngine` detects task metadata changes on re-scan; emits warning; does not apply scheduling changes | `tests/test_reload.py` or `tests/test_task_reload.py` (warning emitted, schedule unchanged, logic reloaded) |
| B09-S13 | Not Started | `mcp-serve` stdio transport support | Wire `mcp.transport` config value through to `mcp_server.run()`; add `--transport` CLI flag override; REPL always SSE | `tests/test_mcp_provider.py` or `tests/test_mcp_transport.py` (stdio config, CLI flag override, REPL SSE enforcement) |
| B09-S14 | Not Started | ADR-0006 and ADR-0007 | Create `docs/decisions/0006-application-server-boundary.md` and `docs/decisions/0007-managed-tasks-design-decisions.md` | Docs review |
| B09-S15 | Not Started | Public API exports and example files | Update `__init__.py` exports (remove embedding); new example file demonstrating a task function | `tests/test_packaging_contract.py` (export assertions); example runs via `brimley invoke` |
| B09-S16 | Not Started | Documentation updates | Update all docs per Section 6 table: high-level design, python functions, functions, REPL admin commands, configuration, discovery spec, security note, `brimley build` experimental marking | Docs conformance review |
| B09-S17 | Not Started | Version bump, CHANGELOG, doc scan gate | `pyproject.toml` → 0.9.0; `CHANGELOG.md`; stale version refs; reference maps; `examples/README.md` | Full suite pass |
| B09-S18 | Not Started | Final validation and release gate | Full test suite; regression check; review approval | Full suite pass |

Status values: `Not Started` | `In Progress` | `Completed` | `Blocked`

---

## Step Details

### B09-S1: Roadmap Renumbering (File Renames + Content Updates)

**Files (expected):**
- `docs/roadmap/brimley-0.9-mocking-framework-and-mcp-interactivity.md` → rename to `brimley-0.10-mocking-framework-and-mcp-interactivity.md`
- `docs/roadmap/brimley-0.10-testing-framework.md` → rename to `brimley-0.11-testing-framework.md`
- `docs/roadmap/brimley-0.11-duckdb-introspection-and-repl-analytics.md` → rename to `brimley-0.12-duckdb-introspection-and-repl-analytics.md`
- `docs/roadmap/brimley-0.12-smart-caching-and-invalidation.md` → rename to `brimley-0.13-smart-caching-and-invalidation.md`
- `docs/roadmap/brimley-0.13-plugin-architecture-custom-function-types.md` → rename to `brimley-0.14-plugin-architecture-custom-function-types.md`
- `docs/roadmap/index.md` — insert v0.9 entry, renumber v0.9→v0.10 through v0.14→v0.15
- `docs/roadmap/copilot-schema-reference-guide.md` — `"v0.9 Manifest"` → `"v0.15 Manifest"`
- `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — update forward references (v0.9→v0.10)
- `docs/roadmap/brimley-0.7-api-functions.md` — update forward references
- `docs/roadmap/brimley-0.7-cli-functions.md` — update forward references
- `docs/decisions/0001-swap-di-and-mocking-order.md` — `"0.9 Mocking"` → `"0.10 Mocking"`
- `docs/decisions/0002-accelerate-api-cli-to-v0.7.md` — renumber references
- `docs/decisions/0004-defer-plugin-architecture-to-v0.13.md` — renumber to v0.14; consider renaming file
- `docs/decisions/0005-defer-manifest-to-v0.14.md` — renumber to v0.15; consider renaming file
- `docs/decisions/README.md` — update version references
- `docs/brimley-api-functions.md` — `"v0.9 Mocking"` → `"v0.10 Mocking"`
- `docs/brimley-cli-functions.md` — `"v0.9 Mocking"` → `"v0.10 Mocking"`
- `docs/brimley-high-level-design.md` — `"v0.9 Mocking"` → `"v0.10"` (if not already done)

**Implementation notes:**
- This is a pure documentation step — no code changes.
- Perform file renames first, then content updates. This avoids broken internal links during the process.
- Each renamed spec file needs its H1 title and self-referencing version numbers updated (see Section 7 of the roadmap spec for the exact substitution table).
- Cross-referencing files (v0.7, v0.8 specs, ADRs, core docs) need forward-reference updates.
- The `index.md` renumbering is the most complex: insert v0.9 entry, bump all subsequent version headers and file links, update "Path to v1.0" reference.

**Definition of done:**
- All roadmap spec files renamed per the Section 7 table.
- All H1 titles and self-referencing version numbers updated in renamed files.
- `index.md` has a new v0.9 entry and all subsequent versions renumbered.
- All cross-references in v0.7/v0.8 specs, ADRs, and core docs updated.
- No broken internal doc links (spot-check navigation).

---

### B09-S2: Remove Embedding Support

**Files (expected):**
- `src/brimley/__init__.py` — remove `BrimleyRuntimeController` from `__all__` and exports
- `src/brimley/core/` — remove or deprecate `BrimleyRuntimeController` class (if it exists as a separate module)
- `docs/brimley-embedded-deployments-and-port-management.md` — archive (move to `docs/archive/`) or add deprecation header pointing to ADR-0006
- `tests/test_packaging_contract.py` — update to assert `BrimleyRuntimeController` is no longer exported

**Implementation notes:**
- The embedding model (`BrimleyRuntimeController`) is being removed as a supported deployment. The class may still exist internally if other code depends on it, but it must not be part of the public API.
- If `BrimleyRuntimeController` is used internally (e.g., by the CLI boot path), it can remain as a private implementation detail — just remove the public export.
- Move `brimley-embedded-deployments-and-port-management.md` to `docs/archive/` with a header: `> **Archived (v0.9):** This deployment model is removed as of v0.9. See [ADR-0006](../decisions/0006-application-server-boundary.md).`
- The three supported modes going forward are: `repl`, `mcp-serve`, and `invoke`.

**Definition of done:**
- `BrimleyRuntimeController` is not importable from the top-level `brimley` package.
- Embedded deployment doc is archived with a deprecation header.
- Existing tests pass (no regression from removal).
- `test_packaging_contract.py` asserts the removal.

---

### B09-S3: Human-Time Parser Utility

**Files (expected):**
- `src/brimley/utils/time_parser.py` (new)
- `tests/test_time_parser.py` (new)

**Implementation notes:**
- Parse human-readable duration strings into total seconds (float): `"30s"` → 30.0, `"5m"` → 300.0, `"1h 30m"` → 5400.0, `"500ms"` → 0.5.
- Supported units: `ms` (milliseconds), `s` (seconds), `m` (minutes), `h` (hours). Multiple units can be combined: `"1h 30m 15s"`.
- Also parse retry_interval formats and return a structured result:
  - `"10s exponential"` or `"10s ex"` → base=10.0, strategy="exponential"
  - `"10s x1.5"` → base=10.0, strategy="multiplier", factor=1.5
  - `"10s"` → base=10.0, strategy="fixed"
- Validation: reject negative values, reject intervals below 1 second (for `interval` usage — the caller enforces the minimum, not the parser itself). Raise `ValueError` with a clear message for unparseable strings.
- Keep the parser simple — no external dependencies. Use regex-based extraction.

**Definition of done:**
- `parse_duration("1h 30m")` returns `5400.0`.
- `parse_retry_interval("10s exponential")` returns a structured result with base, strategy, and optional factor.
- Invalid strings raise `ValueError` with a clear message.
- Edge cases tested: `"500ms"`, `"0s"`, `"1s"`, combined units, whitespace variants.
- All parser tests pass.

---

### B09-S4: Task Metadata Model and @function Extension

**Files (expected):**
- `src/brimley/core/models.py` — add `TaskConfig` Pydantic model
- `src/brimley/__init__.py` — extend `@function` decorator to accept `task` dict
- `src/brimley/core/models.py` — `PythonFunction` / `BrimleyFunction` gains optional `task: Optional[TaskConfig]` field
- `tests/test_task_models.py` (new) — model validation tests
- `tests/test_decorators.py` — extend with `task` parameter tests

**Implementation notes:**
- `TaskConfig` (Pydantic model): `interval: str` (required), `immediate: bool = False`, `retries: Optional[int] = None` (None = unlimited), `retry_interval: str = "1s exponential"`.
- The `@function` decorator's `_brimley_meta` attachment gains an optional `task` key. When `task={...}` is passed, the decorator stores the raw dict; the Scanner's AST phase will parse it into a `TaskConfig` on the model.
- `BrimleyFunction` (or `PythonFunction`) gains `task: Optional[TaskConfig] = None`. Functions with a non-None `task` are task functions.
- Validation on `TaskConfig`: `interval` must be a non-empty string (actual duration validation happens at scan time via the human-time parser). `retries` must be >= 0 if set. `retry_interval` must be a non-empty string.

**Definition of done:**
- `TaskConfig` model validates correctly: required `interval`, optional fields with defaults.
- `@function(name="x", task={"interval": "5m"})` attaches task metadata to the decorated function.
- `BrimleyFunction` with `task` field populated is distinguishable from non-task functions.
- Invalid `TaskConfig` values (e.g., negative `retries`) rejected by Pydantic validation.
- All model and decorator tests pass.

---

### B09-S5: Scanner AST Extraction and Quarantine Rules

**Files (expected):**
- `src/brimley/discovery/python_parser.py` — extract `task` kwargs from `@function` decorator AST node
- `src/brimley/discovery/scanner.py` — implement 4 quarantine rules for task functions
- `tests/test_task_discovery.py` (new) — AST extraction and quarantine rule tests

**Implementation notes:**
- **AST extraction**: When `_find_brimley_decorators()` encounters a `@function` call with a `task` keyword argument, extract the dict literal from the AST. Parse the dict keys (`interval`, `immediate`, `retries`, `retry_interval`) into `TaskConfig` metadata on the `PythonFunction` model.
- **Quarantine Rule 1 — MCP Prohibition**: If a function has both `task` and `mcpType`, skip it and emit: `[Scanner] Skipping '<name>': task functions cannot be MCP objects. Remove mcpType or task configuration.`
- **Quarantine Rule 2 — Signature Constraint**: Task functions may only accept `BrimleyContext` and `Depends()` parameters. If non-injectable positional arguments are detected, skip with warning: `[Scanner] Skipping '<name>': task functions may only accept BrimleyContext and Depends() parameters.`
- **Quarantine Rule 3 — Async Validation**: Task functions must be `async def`. If `ast.FunctionDef` (not `ast.AsyncFunctionDef`), skip with warning.
- **Quarantine Rule 4 — Interval Minimum**: Parse `interval` via the human-time parser. If < 1 second, skip with warning.
- All quarantine rules are soft failures: the function is skipped (not registered), a warning is logged, and the rest of the server starts normally.

**Definition of done:**
- `task` kwargs extracted from `@function` AST node and attached to scanner output.
- Each quarantine rule independently tested: function is skipped, warning is emitted, other functions are unaffected.
- Valid task functions (async, no extra args, no mcpType, interval >= 1s) pass all rules and are registered normally.
- Combined violations (e.g., both MCP + sync) produce a single skip with the first-matched warning.
- All scanner tests pass; no regression in non-task function scanning.

---

### B09-S6: TaskScheduler Core (Daemon Thread + Event Loop)

**Files (expected):**
- `src/brimley/core/task_scheduler.py` (new)
- `tests/test_task_scheduler.py` (new)

**Implementation notes:**
- `TaskScheduler` is a DI-managed singleton that runs on a **dedicated daemon thread** with its own `asyncio` event loop. This is consistent with the existing patterns for the auto-reload watcher and embedded MCP server thread.
- **`start(tasks: List[BrimleyFunction])`**: receives the list of task functions from the registry. For each task, creates an asyncio task on the scheduler's event loop that:
  1. If `immediate=True`, executes the first iteration immediately.
  2. Awaits `asyncio.sleep(interval_seconds)` between iterations.
  3. Calls `Dispatcher.run(func_name)` for each iteration (full DI resolution path).
- **`stop()`**: sends cancellation to all running task coroutines, awaits up to 30 seconds, then hard-cancels remaining.
- The scheduler is **instantiated but not started** in `invoke` mode.
- All `immediate=True` tasks launch concurrently once the server is "Ready" — no guaranteed ordering.
- Thread: `threading.Thread(daemon=True)` with its own `asyncio.new_event_loop()`.

**Definition of done:**
- `TaskScheduler.start()` launches periodic execution for all task functions.
- `TaskScheduler.stop()` cancels all tasks within the grace period.
- `immediate=True` tasks execute their first iteration at startup.
- Scheduler runs on a daemon thread (does not block process exit).
- Task execution goes through `Dispatcher.run()` (full DI path).
- Not started in `invoke` mode (verified by test).
- All scheduler core tests pass.

---

### B09-S7: Retry Policy Implementation

**Files (expected):**
- `src/brimley/core/task_scheduler.py` — add retry logic to the per-task execution loop
- `tests/test_task_scheduler.py` — extend with retry tests

**Implementation notes:**
- When a task iteration raises an unhandled exception, the scheduler enters retry mode:
  - **Exponential** (`"10s exponential"` or `"10s ex"`): delay doubles each retry — 10s, 20s, 40s, 80s, ... capped at `min(computed_delay, interval)`.
  - **Multiplier** (`"10s x1.5"`): delay multiplied by factor — 10s, 15s, 22.5s, ... capped at `interval`.
  - **Fixed** (`"10s"`): constant delay — 10s, 10s, 10s, ...
- **Backoff ceiling**: retry delay never exceeds the task's own `interval`.
- **Reset**: a single successful iteration resets the retry counter and backoff delay to zero.
- **Exhaustion**: if `retries` is set and the counter is exhausted, the task stops retrying and waits for the next normal scheduled interval. Logged as WARNING.
- **Unlimited retries**: if `retries` is `None`, backoff continues indefinitely (capped at `interval`).
- All failures logged with `correlation_id` to `logs.jsonl`.

**Definition of done:**
- Exponential backoff doubles correctly and caps at `interval`.
- Multiplier backoff multiplies by the given factor and caps at `interval`.
- Fixed retry uses constant delay.
- Successful iteration resets retry state.
- Exhausted retries stop and wait for next scheduled interval.
- Unlimited retries continue indefinitely with capped backoff.
- All retry tests pass.

---

### B09-S8: Overlap Prevention and Diagnostic Warning

**Files (expected):**
- `src/brimley/core/task_scheduler.py` — add overlap guard and skip counter
- `tests/test_task_scheduler.py` — extend with overlap tests

**Implementation notes:**
- **Overlap guard**: before starting a scheduled iteration, check if the previous iteration is still running. If so, skip this iteration. This is internal to the `TaskScheduler` loop — manual invocations via `brimley invoke` or REPL are not subject to this guard.
- **`consecutive_skip_count`**: tracked per task. After 3 consecutive scheduler-initiated skips, emit WARNING: `[TaskScheduler] Task 'X' has been running longer than its interval for 3 consecutive iterations. Consider increasing the interval or optimizing the task logic.`
- The counter resets when an iteration completes before the next scheduled start.
- Manual invocations do not affect this counter.

**Definition of done:**
- Overlapping scheduled iterations are skipped (not queued).
- Diagnostic warning emitted after 3 consecutive skips.
- Counter resets on successful completion within interval.
- Manual invocation runs independently of the overlap guard.
- All overlap tests pass.

---

### B09-S9: Three-Phase Shutdown

**Files (expected):**
- `src/brimley/core/container.py` — modify `shutdown()` to insert TaskScheduler.stop() as phase 1
- `src/brimley/core/task_scheduler.py` — `stop()` method with grace period + hard cancel
- `tests/test_container.py` — extend with three-phase ordering tests
- `tests/test_task_scheduler.py` — extend with shutdown tests

**Implementation notes:**
- Modify `BrimleyContainer.shutdown()` to execute in three phases:
  1. **Phase 1**: `TaskScheduler.stop()` — sends cancellation to all running task coroutines, awaits up to 30 seconds, then hard-cancels (`task.cancel()`) any remaining. Logs WARNING for hard-cancelled tasks.
  2. **Phase 2**: `_run_shutdown_hooks()` — existing `@on_shutdown` hooks in reverse declaration order. At this point no task coroutines are running.
  3. **Phase 3**: `_teardown_singletons()` — existing singleton teardown.
- **Backward compatible**: if no `TaskScheduler` is registered (projects without tasks, or `invoke` mode), phase 1 is a no-op.
- The `BrimleyContainer` gains an optional `task_scheduler` reference, set during startup integration (B09-S10).

**Definition of done:**
- Shutdown executes in the correct three-phase order: tasks → hooks → singletons.
- Hard-cancelled tasks produce WARNING log entries.
- Backward compatible: existing projects without tasks shut down normally (no errors, no behavioral change).
- Container shutdown test verifies phase ordering.
- All shutdown tests pass.

---

### B09-S10: Startup Sequence Integration

**Files (expected):**
- `src/brimley/cli/main.py` — wire TaskScheduler into boot path
- `src/brimley/core/task_scheduler.py` — constructor accepts registry reference
- `src/brimley/core/container.py` — accept and store TaskScheduler reference
- `tests/test_startup.py` — extend with TaskScheduler integration tests

**Implementation notes:**
- After `@on_startup` hooks complete and the server is "Ready":
  1. Query `Registry[BrimleyFunction]` for functions with non-None `task` metadata.
  2. Create `TaskScheduler(tasks, dispatcher, context)`.
  3. Call `TaskScheduler.start()` — only in `repl` and `mcp-serve` modes.
  4. Register the scheduler on the container: `container.task_scheduler = scheduler`.
- In `invoke` mode, the `TaskScheduler` is instantiated but `start()` is never called. Phase 1 of shutdown is a no-op.
- The scheduler starts **after** all `@on_startup` hooks, ensuring singletons and startup resources are available.
- If no task functions exist in the registry, the scheduler is still instantiated (for consistency) but has an empty task list.

**Definition of done:**
- TaskScheduler started after `@on_startup` hooks in `repl` and `mcp-serve` modes.
- TaskScheduler not started in `invoke` mode.
- Scheduler registered on container for shutdown coordination.
- Boot sequence works correctly with zero task functions (no errors).
- Tests verify mode-dependent scheduler behavior.

---

### B09-S11: `/tasks` REPL Admin Command

**Files (expected):**
- `src/brimley/cli/repl.py` (or the appropriate REPL command module) — add `/tasks` command handler
- `tests/test_tasks_command.py` (new) — output format and state tests

**Implementation notes:**
- `/tasks` is a read-only introspection command that lists all functions with task metadata and their current scheduling state.
- Output columns: task name, interval, state (`running`, `waiting`, `backoff`), last run time, consecutive failure count, next scheduled run.
- The `TaskScheduler` must expose a `get_task_status()` method (or similar) that returns the current state of each task for the REPL to display.
- If no task functions are registered, display: `No task functions registered.`
- Format as a table (consistent with other REPL admin command output).

**Definition of done:**
- `/tasks` command displays all task functions with correct columns.
- States (`running`, `waiting`, `backoff`) reflect actual scheduler state.
- Empty state handled gracefully.
- Output format is consistent with existing REPL admin commands.
- All REPL command tests pass.

---

### B09-S12: Hot-Reload Warning for Scheduling Changes

**Files (expected):**
- `src/brimley/discovery/reload_engine.py` (or the `PartitionedReloadEngine` module) — detect task metadata changes
- `tests/test_task_reload.py` (new) — warning and immutability tests

**Implementation notes:**
- During a re-scan triggered by the hot-reload watcher, compare the `task` metadata of re-scanned functions against the currently registered metadata.
- If scheduling metadata (`interval`, `immediate`, `retries`, `retry_interval`) has changed, emit: `[Hot-Reload] Task scheduling changes detected for 'X'. Restart Brimley to apply.`
- **Function logic changes**: reloaded normally (the next scheduled iteration executes the updated logic).
- **New task functions**: if a new function with `task` metadata appears during re-scan, scheduling is ignored — it will not be started until restart. Emit warning.
- **Do not apply scheduling changes at runtime** — the immutable schedule rule is enforced by simply not updating the scheduler's internal state.

**Definition of done:**
- Scheduling metadata changes detected and warning emitted.
- Function logic changes reloaded normally.
- New task functions detected with warning; not started until restart.
- Scheduler's internal state unchanged after re-scan with metadata changes.
- All hot-reload tests pass.

---

### B09-S13: `mcp-serve` stdio Transport Support

**Files (expected):**
- `src/brimley/cli/main.py` — add `--transport` CLI flag to `mcp-serve` command
- `src/brimley/mcp/` — wire `transport` config/flag through to `mcp_server.run()`
- `src/brimley/core/models.py` or config module — ensure `mcp.transport` config value is available
- `tests/test_mcp_transport.py` (new) — transport wiring tests

**Implementation notes:**
- The config schema already supports `mcp.transport: "sse" | "stdio"`. Wire this value through to `mcp_server.run()` call in the `mcp-serve` command.
- When `transport` is `"stdio"`: FastMCP uses stdin/stdout — no HTTP server is started, `--host`/`--port` flags are ignored.
- Add a `--transport` CLI flag to `mcp-serve` as an override: `brimley mcp-serve --transport stdio`. CLI flag takes precedence over `brimley.yaml` config.
- **REPL**: the embedded MCP server always uses SSE regardless of the `transport` config value, because stdio would conflict with the interactive terminal. No changes needed to REPL MCP wiring.
- Default transport remains `"sse"` for backward compatibility.

**Definition of done:**
- `brimley mcp-serve` uses the configured `mcp.transport` value.
- `--transport` CLI flag overrides config.
- stdio transport: no HTTP server started, stdin/stdout used.
- REPL MCP server unaffected (always SSE).
- Default remains SSE (backward compatible).
- All transport tests pass.

---

### B09-S14: ADR-0006 and ADR-0007

**Files (expected):**
- `docs/decisions/0006-application-server-boundary.md` (new)
- `docs/decisions/0007-managed-tasks-design-decisions.md` (new)
- `docs/decisions/README.md` — add entries for ADR-0006 and ADR-0007

**Implementation notes:**
- **ADR-0006: Application Server Boundary**
  - Context: embedding model creates event loop contention, lifecycle ambiguity, complicates TaskScheduler.
  - Decision: Brimley is an application server. `BrimleyRuntimeController` removed from public API. Three supported modes: `repl`, `mcp-serve`, `invoke`.
  - Consequences: embedding users must migrate to MCP-based integration (sidecar). Embedded deployments doc archived. TaskScheduler assumes sole event loop ownership.
- **ADR-0007: Managed Tasks Design Decisions**
  - Tasks as functions (`@function(task={...})`) — single registry, single dispatch, testable via `invoke`.
  - Scheduler-only overlap guard — manual invocation bypasses.
  - Three-phase shutdown ordering — tasks before hooks before singletons.
  - 30-second global grace period — per-task timeout deferred (WL-004).
  - Immutable scheduling metadata — logic reloadable, schedule requires restart.
- Follow existing ADR format in `docs/decisions/`.

**Definition of done:**
- Both ADRs created following the existing format.
- `docs/decisions/README.md` updated with ADR-0006 and ADR-0007 entries.
- ADRs cover all key points listed in Section 6 of the roadmap spec.

---

### B09-S15: Public API Exports and Example Files

**Files (expected):**
- `src/brimley/__init__.py` — update `__all__` (confirm embedding exports removed)
- `examples/` — new example demonstrating a task function (e.g., `examples/task_reconciler.py`)
- `examples/README.md` — update version header and add task example entry
- `tests/test_packaging_contract.py` — update import assertions

**Implementation notes:**
- Ensure `BrimleyRuntimeController` is not in `__all__` (done in B09-S2, verify here).
- No new public exports needed for tasks specifically — `@function` already handles the `task` parameter. The `TaskConfig` model may be exported if useful for type hints.
- New example file demonstrating a task function: `@function(name="reconciler", task={"interval": "1m", "immediate": True, "retries": 3, "retry_interval": "5s exponential"})` with a simple async body.
- Update `examples/README.md` with the new example.

**Definition of done:**
- Public API exports are correct (no embedding, task decorator works via existing `@function`).
- New task example file exists and is syntactically valid.
- `examples/README.md` references the new example.
- Packaging contract tests pass.

---

### B09-S16: Documentation Updates

**Files (expected):**
- `docs/brimley-high-level-design.md` — add Managed Tasks subsystem, TaskScheduler Key Component
- `docs/brimley-python-functions.md` — add `task` parameter documentation, task parameters table, retry formats, quarantine rules
- `docs/brimley-functions.md` — add "Task Functions" subsection
- `docs/brimley-repl-admin-commands.md` — document `/tasks` command
- `docs/brimley-configuration.md` — note that tasks are per-function (no `task:` YAML block)
- `docs/brimley-discovery-and-loader-specification.md` — document 4 quarantine rules
- `docs/security/` — task trust boundary note
- `docs/brimley-cli-and-repl-harness.md` — update if `--transport` flag added to `mcp-serve`
- `docs/copilot/copilot-docs-reference.md` — add task/scheduler topic rows and keyword entries
- `README.md` — verify application server framing (done in earlier session, confirm current)

**Implementation notes:**
- Follow the Section 6 Documentation Updates table in the roadmap spec for the full list.
- Mark `brimley build` as experimental in CLI help text, docstring, and any doc references.
- Add keyword index entries for: `task`, `TaskScheduler`, `TaskConfig`, `interval`, `retry_interval`, `managed task`, `overlap`, `/tasks`.

**Definition of done:**
- All documents listed in the Section 6 table are updated.
- `brimley build` marked as experimental.
- Copilot docs reference map includes task/scheduler entries.
- No orphaned "deferred to v0.9" references remaining.
- Documentation is consistent with implemented behavior.

---

### B09-S17: Version Bump, CHANGELOG, Doc Scan Gate

**Files (expected):**
- `pyproject.toml` — version → `0.9.0`
- `CHANGELOG.md` — v0.9.0 entries under Added/Changed/Removed
- `examples/README.md` — version header update
- Various docs — stale version reference sweep

**Implementation notes:**
- CHANGELOG entries:
  - **Added**: Managed Tasks (`@function(task={...})`), `TaskScheduler`, human-time parser, `/tasks` REPL command, `mcp-serve` stdio transport, `--transport` CLI flag, ADR-0006, ADR-0007.
  - **Changed**: Three-phase shutdown (tasks → hooks → singletons), hot-reload detects scheduling metadata changes.
  - **Removed**: `BrimleyRuntimeController` (embedding support removed).
- Doc scan gate per copilot-instructions §8:
  - Baseline headers: update `Docs baseline: 0.8.x` → `0.9.x` in docs with content changes.
  - Stale body-text references: update "deferred to v0.9" → now current.
  - Reference maps: update `brimley-high-level-design.md` §5, `README.md` doc map, `copilot-docs-reference.md`.
  - Feature mentions: TaskScheduler as Key Component in high-level design.
  - Context doc: update if `BrimleyContext` gained new fields.
  - CLI/REPL doc: `/tasks` command, `--transport` flag.

**Definition of done:**
- `pyproject.toml` version is `0.9.0`.
- CHANGELOG has complete v0.9.0 section with Added/Changed/Removed.
- `Docs baseline` headers updated in changed docs.
- No stale "deferred to v0.9" references.
- Doc scan gate checklist completed per copilot-instructions §8.

---

### B09-S18: Final Validation and Release Gate

**Files (expected):**
- None (validation only).

**Implementation notes:**
- Run full test suite.
- Verify no regressions from v0.8.
- Confirm task lifecycle end-to-end: declare task → scan → start scheduler → periodic execution → shutdown.
- Confirm stdio transport works for `mcp-serve`.
- Confirm roadmap renumbering is consistent across all files.
- Review approval required before commit.

**Definition of done:**
- Full test suite green.
- No new warnings or deprecations.
- End-to-end task lifecycle verified.
- Review approval granted.

---

## Acceptance Criteria

- `@function(name="x", task={"interval": "5m"})` declares a managed task that is discovered, registered, and periodically executed by the `TaskScheduler`.
- Task functions are async, accept only `BrimleyContext` and `Depends()` parameters, and are not MCP objects.
- Scanner quarantine rules (MCP prohibition, signature constraint, async validation, interval minimum) skip violating functions with warnings — no server abort.
- `TaskScheduler` runs on a dedicated daemon thread with its own event loop.
- `TaskScheduler` starts only in `repl` and `mcp-serve` modes; skipped in `invoke` mode.
- `immediate=True` tasks execute their first iteration at startup.
- Retry policy works correctly: exponential, multiplier, and fixed backoff with ceiling at `interval`.
- Retry counter resets on success; exhausted retries wait for next scheduled interval.
- Overlap prevention skips scheduled iterations when the previous is still running.
- Diagnostic warning after 3 consecutive scheduler-initiated skips.
- Manual invocation via `brimley invoke` or REPL bypasses overlap guard.
- Three-phase shutdown: TaskScheduler.stop() → @on_shutdown hooks → singleton teardown. 30-second grace period.
- `/tasks` REPL command displays task name, interval, state, last run, failure count, next scheduled run.
- Hot-reload detects scheduling metadata changes and emits warning; schedule is immutable until restart.
- `brimley mcp-serve` supports stdio transport via config and `--transport` CLI flag.
- REPL embedded MCP server always uses SSE.
- `BrimleyRuntimeController` removed from public API.
- Embedded deployments doc archived with deprecation header.
- ADR-0006 and ADR-0007 created per Section 6 requirements.
- All documentation updated per Section 6 table.
- Roadmap files renumbered per Section 7.
- No regressions in existing Python, SQL, template, API, CLI, or MCP function execution.
- No regressions in DI, lifecycle hooks, or secrets resolution.
- `CHANGELOG.md` updated with Added / Changed / Removed entries for v0.9.0.
- `examples/` updated with task example file.
- Version bump performed: `pyproject.toml` updated to `0.9.0`.
- Doc scan gate completed per copilot-instructions §8.
- **Pre-publish gate:** `pyproject.toml` `version` field must reflect `0.9.0` before running `poetry build` / `poetry publish`.

## Risks / Notes

- **Daemon thread event loop**: The `TaskScheduler` runs its own `asyncio` event loop on a daemon thread. This is the same pattern used by the auto-reload watcher and embedded MCP server, but task coroutines may run longer and interact more heavily with shared resources (DB pools, DI container). Mitigation: request-scope isolation per task iteration via `Dispatcher.run()`.
- **Shutdown race conditions**: Tasks may be mid-execution when shutdown starts. The 30-second grace period should be sufficient for most tasks, but long-running reconcilers could be hard-cancelled. Mitigation: WARNING log on hard cancel; per-task timeout deferred to WL-004.
- **Overlap guard precision**: The overlap guard checks a boolean flag per task. If the scheduler's sleep granularity is coarse, there could be a brief window where the flag is checked before the task coroutine fully starts. Mitigation: use `asyncio.Lock` or a similar synchronization primitive per task.
- **Hot-reload detection**: Comparing `TaskConfig` objects between scans requires stable serialization. Pydantic model comparison (equality) should work, but edge cases with float precision in parsed durations could cause false positives. Mitigation: compare raw string values from AST, not parsed floats.
- **stdio transport testing**: Testing actual stdio transport requires subprocess orchestration (sending/receiving on stdin/stdout). Mitigation: test the wiring (config → FastMCP call) rather than full I/O integration.
- **Roadmap renumbering scope**: Section 7 lists many files. Missing a cross-reference update could leave stale version numbers in docs. Mitigation: systematic search for old version numbers after renumbering.
- **Backward compatibility**: Projects without task functions should experience no behavioral change. The `TaskScheduler` is instantiated but starts with an empty task list, and phase 1 of shutdown is a no-op.

## Validation Plan

Run tests in this order:
1. Focused tests for changed module(s): `poetry run python -m pytest tests/test_time_parser.py tests/test_task_models.py tests/test_decorators.py tests/test_task_discovery.py tests/test_task_scheduler.py tests/test_tasks_command.py tests/test_task_reload.py tests/test_mcp_transport.py -v`
2. Adjacent/regression tests: `poetry run python -m pytest tests/test_discovery.py tests/test_container.py tests/test_startup.py tests/test_execution_python.py tests/test_packaging_contract.py tests/test_mcp_provider.py tests/test_context.py -v`
3. Full suite: `poetry run python -m pytest`

Record results:
- Focused: [pass/fail + summary]
- Regression: [pass/fail + summary]
- Full suite: [pass/fail + summary]

---

## Step Notes Log

| Step ID | Date | Changes Made | Deviations | Validation |
|---|---|---|---|---|
| B09-S1 | 3/28/2026 | Renamed 5 roadmap spec files (0.9→0.10, 0.10→0.11, 0.11→0.12, 0.12→0.13, 0.13→0.14). Renamed 2 ADR files (0004→v0.14, 0005→v0.15). Updated H1 titles and self-referencing version numbers in all renamed files. Updated `index.md` with new v0.9 entry and renumbered all subsequent versions. Updated cross-references in v0.7/v0.8 specs, ADR-0001/0002/0004/0005, decisions README, core docs (api-functions, cli-functions), and schema reference guide. | None | Manual grep verification: no stale old-filename references or version mismatches found. |
| B09-S2 | 3/29/2026 | Removed `BrimleyRuntimeController` and `ReloadLifecycleEvent` from `brimley.runtime.__all__`. Added comment noting internal-only status. Archived `docs/brimley-embedded-deployments-and-port-management.md` to `docs/archive/` with v0.9 deprecation header. Added deprecation redirect stub in original location. Added `test_runtime_controller_not_in_public_api` test in `test_packaging_contract.py`. | None | 5 packaging contract tests pass; 58 CLI/runtime regression tests pass. |
| B09-S3 | 3/29/2026 | Created `src/brimley/utils/time_parser.py` with `parse_duration()` (h/m/s/ms units, multi-unit combinations) and `parse_retry_interval()` (fixed/exponential/multiplier strategies). Created `tests/test_time_parser.py` with 35 tests covering valid inputs, edge cases, and error conditions. Fixed retry_interval parser to correctly handle multi-unit bases (e.g. "1h 30m"). | Removed `test_no_space_combined` (no-space multi-unit syntax is not spec-required). | 35/35 tests pass. |
| B09-S4 | 3/29/2026 | Added `TaskConfig` Pydantic model to `core/models.py` (interval, immediate, retries, retry_interval with defaults/validation). Added `task: Optional[TaskConfig] = None` field to `PythonFunction`. Extended `@function` decorator in `__init__.py` to accept `task=` parameter (stored in `_brimley_meta['task']`; omitted when None). | None | 38 tests pass (test_task_models.py + test_decorators.py); 35 DI model regression tests pass. |
| B09-S5 | 3/29/2026 | Updated `python_parser.py` to extract `task` kwarg from `@function` AST (creates `TaskConfig`), set `is_async` flag. Added `is_async` field to `PythonFunction`. Added `_apply_task_quarantine_rules()` to `scanner.py` (4 rules: MCP prohibition, signature constraint, async check, interval minimum). Called quarantine in scanner main loop. New `tests/test_task_discovery.py`: 13 tests covering all rules, valid functions, and regression. | None | 13/13 discovery tests; 41 regression tests pass. |
| B09-S6 | — | — | — | — |
| B09-S7 | — | — | — | — |
| B09-S8 | — | — | — | — |
| B09-S9 | — | — | — | — |
| B09-S10 | — | — | — | — |
| B09-S11 | — | — | — | — |
| B09-S12 | — | — | — | — |
| B09-S13 | — | — | — | — |
| B09-S14 | — | — | — | — |
| B09-S15 | — | — | — | — |
| B09-S16 | — | — | — | — |
| B09-S17 | — | — | — | — |
| B09-S18 | — | — | — | — |

---

## Copilot Execution Protocol

**Plan pointer:** `docs/copilot/current-plan.md` → this file.
**Step execution:** Follow §2 step-by-step — one step at a time, mark In Progress before coding, Completed after tests pass.
**Test-first mandate:** §3 — write or update tests before/simultaneously with implementation.
**Commit protocol:** §5 — tests must pass before presenting; explicit approval required before commit.
