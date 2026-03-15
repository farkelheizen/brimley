# 20260314-brimley-0.6 Plan: Brimley 0.6 Observability and Logging Architecture

> Date: 3/15/2026
> Owner: Copilot
> Branch: [optional-branch-name]
> Related docs: `docs/roadmap/brimley-0.6-logging-architecture.md`, `docs/brimley-configuration.md`, `docs/brimley-context.md`, `docs/brimley-cli-and-repl-harness.md`, `docs/brimley-repl-admin-commands.md`, `docs/brimley-model-context-protocol-integration.md`, `README.md`

This file is intended as a working implementation plan.

## Problem Summary
Brimley 0.6 introduces a new observability architecture centered on structured logging, correlation IDs, and FastMCP unification.

Current implementation and docs do not yet provide a single validated contract for all required logging behaviors: global and module-level thresholds, request-scoped overrides keyed by correlation_id, dual sink behavior (stderr + optional file), and third-party logging interception.

A stepwise implementation plan is needed so runtime behavior, CLI/REPL controls, config models, tests, and canonical docs converge to one enforceable 0.6 contract.

## Goal
Deliver Brimley 0.6 logging/observability as a coherent, test-validated architecture with OTel-aligned trace IDs, deterministic level precedence, and complete user/operator documentation.

## Scope
- In scope: logging config model under `brimley.logging`, Loguru bootstrap/filters, correlation/external trace context propagation, module-level threshold overrides, per-correlation override controls, CLI/REPL log controls, FastMCP/python logging interception, dual sink behavior, tests, docs, migration notes.
- Out of scope: OpenTelemetry exporter SDK integration, distributed tracing backend setup, non-logging observability pillars (metrics/traces exporters), redesign of non-observability runtime APIs.

## Constraints / Requirements
- Treat `docs/roadmap/brimley-0.6-logging-architecture.md` as source of truth for 0.6 logging behavior.
- Preserve MCP safety rule: logs must never contaminate stdout JSON-RPC streams.
- Preserve deterministic precedence order for effective log levels.
- Keep async/thread safety for context propagation via `ContextVar` semantics.
- Maintain compatibility with provider-first MCP architecture from 0.5.
- Use Poetry commands (`poetry run ...`) for all validation/test execution.
- Prefer `poetry run python -m pytest ...` for test execution in this repository (current local `poetry run pytest` entrypoint has shown environment mismatch on 2026-03-15).
- Keep documentation and implementation in lockstep before step completion.

---

## Implementation Plan

| Step ID | Status | Goal | Planned Changes | Test Coverage |
|---|---|---|---|---|
| B06-S1 | Completed | Define logging domain models and config loading contract | Add/extend settings models for `brimley.logging`, including global/module/file/managed controls and validation | `tests/test_config_loader.py`, `tests/test_context_config.py`, new logging config model tests |
| B06-S2 | Completed | Implement logging bootstrap and sink wiring | Fixed CLI startup safety test assertions (CliRunner sys-pinning); stderr sink confirmed for `invoke` and `mcp-serve` | `tests/test_logging_init.py`, `tests/test_cli.py` startup logging safety checks |
| B06-S3 | Completed | Implement correlation and external trace context propagation | Added ContextVar helpers in `infrastructure/logging.py`; `BrimleyContext.correlation_id` + `external_trace_id` properties; Dispatcher sets correlation ID at dispatch entry | new `tests/test_logging_context.py` |
| B06-S4 | Completed | Implement module-level threshold filtering | Added `_module_threshold` + `_make_sink_filter` with longest-prefix match; both sinks now use filter | new `tests/test_logging_filtering.py` |
| B06-S5 | Completed | Add per-correlation level overrides | Added thread-safe `_correlation_overrides` dict + set/clear/get helpers; integrated into sink filter | new `tests/test_logging_request_overrides.py` |
| B06-S6 | Completed | Integrate third-party logging interception | Added `InterceptHandler` + `install_intercept_handler`; called from `initialize_logging` | new `tests/test_logging_intercept.py` |
| B06-S7 | Completed | Add CLI and REPL logging controls | Added `--log-level`/`--log-module` to invoke/repl/repl-daemon/mcp-serve; REPL commands `/log-level`, `/log-modules`, `/log-reset`, `/log-level-for-id` | new `tests/test_repl_logging_commands.py` |
| B06-S8 | Completed | Ensure caller attribution and dispatcher depth correctness | Added `get_logger(depth)` helper; `InterceptHandler` uses frame-walking depth; Dispatcher propagates external_trace_id | new `tests/test_logging_caller_attribution.py` |
| B06-S9 | In Progress | Update docs and operator guidance | Align docs/README with final logging contract, config examples, precedence, REPL commands, MCP/OTel notes | docs conformance review + grep verification |
| B06-S10 | Not Started | Validate, harden, and hand off | Run focused/regression/full suites, record validation and residual risks, finalize release-ready notes | full `poetry run pytest` + validation summary |

Status values: `Not Started` | `In Progress` | `Completed` | `Blocked`

---

## Step Details

### B06-S1 Logging Config Models
**Files (expected):**
- `src/brimley/config/models.py` (or logging-specific model module)
- `src/brimley/config/loader.py`
- `src/brimley/context/` model wiring

**Implementation notes:**
- Define strict schema for `brimley.logging` with defaults:
  - `level` (global)
  - `modules` (module-prefix map)
  - `file.path`, `file.level`, `file.format`, `file.rotation`, `file.retention`
  - `managed`
- Ensure case-insensitive level normalization and clear diagnostics for invalid values.

**Definition of done:**
- Config loader produces deterministic logging settings with validated defaults and actionable errors.

### B06-S2 Logging Bootstrap and Sinks
**Files (expected):**
- `src/brimley/infrastructure/logging.py` (new)
- `src/brimley/cli/main.py`
- `src/brimley/runtime/controller.py` (if runtime bootstrap path needs logging init)

**Implementation notes:**
- Remove default Loguru sink and always attach stderr sink.
- Add optional file sink with rotation/retention and JSONL serialize support.
- Ensure `managed: false` bypass behavior is deterministic and documented.

**Remaining checklist for completion:**
- Add/confirm CLI-level startup safety tests that assert no logging output is routed to stdout in MCP-sensitive flows.
- Record focused + adjacent validation output in Step Notes Log using Poetry module-form pytest commands.
- Update `docs/copilot/current-plan.md` to move current step only after validation is fully captured.

**Definition of done:**
- Runtime consistently emits stderr logs without stdout contamination and optional file sink behaves per config.

### B06-S3 Correlation + External Trace IDs
**Files (expected):**
- `src/brimley/execution/dispatcher.py`
- `src/brimley/context/context.py`
- `src/brimley/mcp/fastmcp_provider.py`
- `src/brimley/infrastructure/logging.py`

**Implementation notes:**
- Implement get-or-create `correlation_id` at top-level dispatch.
- Add `external_trace_id` from FastMCP `request_id` when available; fallback to local correlation ID.
- Expose both as read-only context properties.

**Definition of done:**
- Every request log record includes stable correlation and external trace fields with correct fallback semantics.

### B06-S4 Module-Level Threshold Filtering
**Files (expected):**
- `src/brimley/infrastructure/logging.py`

**Implementation notes:**
- Implement level threshold function using longest-prefix module match.
- Do not use `enable/disable` as level semantics.
- Apply same logic to stderr and file sinks with sink-specific defaults.

**Definition of done:**
- Module-level overrides behave Log4J-style and are deterministic across overlapping prefixes.

### B06-S5 Per-Correlation Overrides
**Files (expected):**
- `src/brimley/infrastructure/logging.py`
- `src/brimley/execution/dispatcher.py`
- `src/brimley/cli/repl.py`

**Implementation notes:**
- Add in-memory override registry keyed by `correlation_id`.
- Integrate with effective threshold resolution.
- Ensure cleanup on request completion and explicit REPL clear path.

**Definition of done:**
- DEBUG can be enabled for one in-flight correlation ID without changing levels for concurrent requests.

### B06-S6 Intercept Third-Party Logs
**Files (expected):**
- `src/brimley/infrastructure/logging.py`
- `src/brimley/mcp/fastmcp_provider.py`

**Implementation notes:**
- Add stdlib logging intercept handler forwarding to Loguru.
- Preserve logger name/module for filter matching.
- Avoid double logging and handler loops.

**Definition of done:**
- FastMCP and dependency logs appear in the same structured stream with Brimley context fields.

### B06-S7 CLI and REPL Controls
**Files (expected):**
- `src/brimley/cli/main.py`
- `src/brimley/cli/repl.py`
- `src/brimley/cli/formatter.py`

**Implementation notes:**
- Add CLI flags for global/module overrides.
- Add REPL commands for global/module/request-level controls and introspection/reset.
- Preserve precedence and apply changes without restart.

**Definition of done:**
- Operators can change effective logging immediately during REPL sessions and via CLI startup options.

### B06-S8 Caller Attribution Correctness
**Files (expected):**
- `src/brimley/execution/dispatcher.py`
- `src/brimley/execution/` runners
- `src/brimley/infrastructure/logging.py`

**Implementation notes:**
- Ensure logs attribute to user-land callsites where feasible.
- Keep fallback attribution deterministic when depth cannot be resolved.

**Definition of done:**
- User-facing logs avoid misleading dispatcher-only callsite attribution.

### B06-S9 Documentation and Migration Alignment
**Files (expected):**
- `README.md`
- `docs/brimley-configuration.md`
- `docs/brimley-context.md`
- `docs/brimley-cli-and-repl-harness.md`
- `docs/brimley-repl-admin-commands.md`
- `docs/brimley-model-context-protocol-integration.md`
- `docs/brimley-diagnostics-and-error-reporting.md`
- `docs/roadmap/brimley-0.6-logging-architecture.md`

**Implementation notes:**
- Add canonical `brimley.logging` schema and examples.
- Document precedence order and runtime controls.
- Document OTel/external trace mapping and JSONL fields.
- Document operational guidance for request-scoped debugging and performance impact.

**Definition of done:**
- No contradictions remain between roadmap spec, canonical docs, and runtime behavior.

### B06-S10 Validation and Handoff
**Files (expected):**
- plan notes + validation summary artifacts

**Implementation notes:**
- Execute focused -> regression -> full suite order.
- Record test outcomes and any known non-blocking warnings.

**Definition of done:**
- All acceptance criteria are met and validation evidence is recorded in this plan.

---

## Acceptance Criteria
- `brimley.logging` config is fully modeled, validated, and documented.
- Logs are always written to stderr safely for MCP; stdout protocol stream remains clean.
- Optional file sink supports level, format, rotation, and retention as specified.
- Global + module-level thresholds work deterministically and match documented precedence.
- Per-correlation_id overrides work for targeted in-flight debugging and auto-cleanup.
- `correlation_id` and `external_trace_id` are available in log records and context.
- FastMCP/stdlib logging is unified into Brimley logging without duplicate loops.
- CLI and REPL logging controls are implemented and documented.
- Caller attribution improvements are validated for user-facing execution logs.
- Documentation updates are complete across roadmap spec, docs/, and README.

## Risks / Notes
- Log filtering on hot async paths can add overhead if implemented inefficiently.
- Third-party interception can create duplicate or recursive logging if handler setup is incorrect.
- Request-level overrides can leak if cleanup paths are incomplete during exceptions.

Mitigations:
- Keep filter logic minimal and pre-normalize level values.
- Add explicit recursion/duplicate guardrails in intercept handler setup.
- Enforce try/finally cleanup in dispatcher/request lifecycle and test exception paths.

## Validation Plan
Run tests in this order:
1. Focused tests for changed module(s): `poetry run python -m pytest tests/test_config_loader.py tests/test_context_config.py tests/test_logging_init.py tests/test_mcp_provider.py tests/test_cli.py tests/test_repl.py -k 'logging or trace or correlation or mcp'`
2. Adjacent/regression tests: `poetry run python -m pytest tests/test_execution.py tests/test_execution_python.py tests/test_execution_sql.py tests/test_diagnostics_display.py tests/test_runtime_reload_contracts.py`
3. Full suite: `poetry run python -m pytest`
4. Docs conformance verification: `rg -n "brimley\.logging|log-level|external_trace_id|correlation_id|jsonl|rotation|retention" docs README.md docs/roadmap` (fallback when `rg` is unavailable: `grep -RInE "brimley\.logging|log-level|external_trace_id|correlation_id|jsonl|rotation|retention" docs README.md docs/roadmap`)

Record results:
- Focused: [partial] `poetry run python -m pytest tests/test_logging_init.py -q` -> pass (4 passed); `poetry run python -m pytest tests/test_cli.py -k logging -q` -> no matching tests (47 deselected, exit code 5)
- Regression: [pass/fail + summary]
- Full suite: [pass/fail + summary]

---

## Step Notes Log (update as work progresses)

### B06-S1 Notes
- Changes made:
  - Added structured logging models in `src/brimley/core/models.py`: `LoggingSettings` and `LoggingFileSettings` under `FrameworkSettings.logging`.
  - Added log-level normalization and validation for global/module/file levels (`TRACE|DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL`).
  - Added backward-compatibility behavior mapping legacy `brimley.log_level` into `brimley.logging.level` when explicit logging level is absent.
  - Added focused tests in `tests/test_context_config.py` for logging defaults, normalization, legacy mapping, and validation failures.
  - Added focused loader test in `tests/test_config_loader.py` to assert `brimley.logging` section passthrough.
- Deviations: none
- Validation:
  - `poetry run pytest tests/test_config_loader.py tests/test_context_config.py` -> pass (18 passed)

### B06-S2 Notes
- Changes made:
  - Fixed two failing CLI stdout-safety tests: added `_PinnedSys` monkeypatch to pin `logging_infra.sys` to pre-CliRunner `sys.stderr`/`sys.stdout` so assertions are not affected by CliRunner's stderr redirection.
  - `test_invoke_startup_logging_uses_stderr_sink_not_stdout` and `test_mcp_serve_startup_logging_uses_stderr_sink_not_stdout` now pass.
- Deviations: none
- Validation:
  - `poetry run python -m pytest tests/test_logging_init.py tests/test_cli.py -k logging -q` -> pass (6 passed)

### B06-S3 Notes
- Changes made:
  - Added `_correlation_id` and `_external_trace_id` ContextVars in `infrastructure/logging.py`.
  - Added `get_correlation_id`, `get_or_create_correlation_id`, `set_correlation_id`, `get_external_trace_id`, `set_external_trace_id` helpers.
  - Added `correlation_id` and `external_trace_id` read-only properties on `BrimleyContext`.
  - Updated `Dispatcher.run()` to call `get_or_create_correlation_id()` at entry and extract `external_trace_id` from FastMCP context when available.
  - Sink filter injects both IDs into every log record via `setdefault`.
- Deviations: none
- Validation:
  - `poetry run python -m pytest tests/test_logging_context.py -q` -> pass (11 passed)

### B06-S4 Notes
- Changes made:
  - Added `_LEVEL_ORDER` tuple and `_module_threshold` function (longest-prefix matching).
  - Added `_make_sink_filter` factory that creates a Loguru filter function injecting IDs and applying module/global level gating.
  - Both stderr and file sinks in `initialize_logging` now use this filter.
- Deviations: none
- Validation:
  - `poetry run python -m pytest tests/test_logging_filtering.py -q` -> pass (14 passed)

### B06-S5 Notes
- Changes made:
  - Added `_correlation_overrides` dict and `_overrides_lock` for thread safety.
  - Added `set_correlation_level_override`, `clear_correlation_level_override`, `get_correlation_overrides` helpers.
  - Sink filter checks `_correlation_overrides` for the current record's correlation ID.
- Deviations: Used a global dict (not ContextVar) since overrides must be visible across all threads to affect concurrent requests.
- Validation:
  - `poetry run python -m pytest tests/test_logging_request_overrides.py -q` -> pass (9 passed)

### B06-S6 Notes
- Changes made:
  - Added `InterceptHandler(logging.Handler)` class that routes stdlib log records into Loguru via frame-walking depth calculation.
  - Added `install_intercept_handler` function; called automatically from `initialize_logging` when managed=True.
  - Idempotent: will not add duplicate handlers on repeat calls.
- Deviations: none
- Validation:
  - `poetry run python -m pytest tests/test_logging_intercept.py -q` -> pass (8 passed)

### B06-S7 Notes
- Changes made:
  - Added `_parse_log_module_spec` helper to `main.py` for parsing `MODULE:LEVEL` specs.
  - Added `--log-level` and `--log-module` token parsing to `invoke`, `mcp-serve`, `repl`, and `repl-daemon` commands.
  - Updated `BrimleyREPL.__init__` to accept `global_level_override` and `module_overrides` params.
  - Added REPL commands: `/log-level`, `/log-modules`, `/log-reset`, `/log-level-for-id` with handlers `_cmd_log_level`, `_cmd_log_modules`, `_cmd_log_reset`, `_cmd_log_level_for_id`.
  - Updated `/help` to list new commands.
- Deviations: none
- Validation:
  - `poetry run python -m pytest tests/test_repl_logging_commands.py -q` -> pass (19 passed)

### B06-S8 Notes
- Changes made:
  - Added `get_logger(depth)` helper to `infrastructure/logging.py` returning `_logger.opt(depth=depth)`.
  - `InterceptHandler.emit` already uses frame-walking depth to find user-land callsite.
  - `Dispatcher.run` propagates `external_trace_id` from FastMCP request context.
- Deviations: Runners do not currently emit any Loguru log records themselves, so no changes to runner files were needed. `get_logger` is exported for future runner use.
- Validation:
  - `poetry run python -m pytest tests/test_logging_caller_attribution.py -q` -> pass (4 passed)

### B06-S8 Notes
- Changes made:
  - Added `get_logger(depth)` helper to `infrastructure/logging.py` returning `_logger.opt(depth=depth)`.
  - `InterceptHandler.emit` already uses frame-walking depth to find user-land callsite.
  - `Dispatcher.run` propagates `external_trace_id` from FastMCP request context.
- Deviations: Runners do not currently emit any Loguru log records themselves, so no changes to runner files were needed. `get_logger` is exported for future runner use.
- Validation:
  - `poetry run python -m pytest tests/test_logging_caller_attribution.py -q` -> pass (4 passed)

### B06-S9 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B06-S10 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

---

## Copilot Execution Protocol
When Copilot uses this plan:
1. Set current step to `In Progress` before coding.
2. Implement only the current step scope.
3. Run listed tests for the step.
4. Update step status to `Completed` (or `Blocked`) with notes.
5. Continue to next step only after validation is recorded.
