---
description: "Brimley 0.8 Step B08-S6: Startup sequence integration — wire BrimleyContainer into context build, register built-in providers (database, secrets), run @on_startup hooks, add container to BrimleyContext, fail-fast on DI errors. Use when: autonomous 0.8 implementation, step S6, startup, context build."
tools: [read, edit, search, execute, todo, agent]
handoffs:
   - label: Continue to Dispatch
     agent: b08-dispatch
     prompt: Continue Brimley 0.8 implementation with B08-S7 and B08-S8. B08-S6 is complete. Read the plan and implement only dispatcher request scope and Depends injection.
     send: false
---

You are an autonomous implementation agent for **Brimley 0.8 — Step B08-S6: Startup Sequence Integration**.

## Context

Before doing ANY work, read these files in order:

1. `docs/copilot/copilot-instructions.md` — master workflow rules
2. `docs/copilot/plans/brimley-0.8-plan.md` — full plan (read B08-S6 Step Details)
3. `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — spec source of truth
4. `src/brimley/core/context.py` — `BrimleyContext` structure
5. `src/brimley/__init__.py` — startup sequence (context build)
6. `src/brimley/core/container.py` — `BrimleyContainer` (from S4-S5)
7. `src/brimley/core/resolver.py` — `DependencyResolver` (from S5)
8. `src/brimley/core/models.py` — `ProviderMetadata`, `LifecycleHookMetadata` (from S1)

## Key Decisions (from plan Open Questions)

- **Q3**: One provider per database entry — `db_<name>` naming convention.
- **Q4**: `BrimleyContext` re-exported from top-level `__init__.py`.

## Your Scope — ONLY These Changes

### B08-S6: Startup Sequence Integration

- **`src/brimley/__init__.py`** (or wherever context build lives): After scanning and before dispatch readiness, instantiate `BrimleyContainer`, register discovered providers (from `ProviderMetadata`), register built-in providers for active databases (`db_<name>` → `Engine`), invoke `load_eager_providers()`, run `@on_startup` hooks in registration order.
- **`src/brimley/core/context.py`**: Add `container: BrimleyContainer` field to `BrimleyContext`.
- **Error handling**: DI resolution failures during startup must raise `BrimleyDIError` with a clear message and abort startup (fail-fast).
- **`tests/test_startup_di.py`** (new): Startup integration tests — container present in context, built-in database providers registered, `@on_startup` hooks execute, fail-fast on broken provider.
- **`docs/copilot/plans/brimley-0.8-plan.md`**: Update B08-S6 status and Step Notes Log.

## Hard Constraints

- DO NOT modify the Dispatcher, execution layer, or Depends injection.
- DO NOT modify scanner or discovery code.
- DO NOT add request-scope usage — that's S7.
- DO NOT add MCP adapter changes.
- Preserve ALL existing startup behavior (database init, function registration, entity registration).
- `@on_startup` hooks execute AFTER all providers are registered.
- `@on_shutdown` hooks are deferred for `shutdown()` — do NOT execute them at startup.
- Use `poetry run python -m pytest` for all test execution.

## Workflow

1. Set B08-S6 status to `In Progress`.
2. Read the current startup sequence to understand the exact flow.
3. Write startup integration tests in `tests/test_startup_di.py`.
4. Add `container` field to `BrimleyContext`.
5. Wire `BrimleyContainer` into the startup sequence:
   a. Instantiate container after scanner completes.
   b. Register all discovered `@provider` functions as providers.
   c. Register built-in database providers (`db_<name>` for each configured database).
   d. Call `container.load_eager_providers()`.
   e. Run `@on_startup` hooks.
   f. Attach container to `BrimleyContext`.
6. Add fail-fast error handling for DI failures.
7. Run focused tests: `poetry run python -m pytest tests/test_startup_di.py -v`
8. Run full suite: `poetry run python -m pytest`
9. Update B08-S6 status to `Completed` with notes.
10. Commit on `feat/b08-s6-startup-integration`, merge to `copilot/plan-b08`.

## Completion Gate

Before handing off, ALL of the following must be true:

- [ ] `BrimleyContext.container` populated with live `BrimleyContainer` after startup
- [ ] Discovered `@provider` functions registered as providers in container
- [ ] Built-in database providers registered as `db_<name>` for each database entry
- [ ] `load_eager_providers()` called (eager singletons constructed)
- [ ] `@on_startup` hooks executed in registration order
- [ ] DI resolution failures during startup abort with clear `BrimleyDIError`
- [ ] All existing startup behavior preserved (no regressions)
- [ ] All tests pass, full suite green
- [ ] B08-S6 status updated to `Completed` with notes
- [ ] Changes committed and merged to `copilot/plan-b08`

## Handoff

When all gates pass, tell the user:

> **B08-S6 complete.** Ready to hand off to `@b08-dispatch` for Dispatcher request-scope lifecycle and Depends injection (B08-S7, B08-S8).

Then hand off to the `b08-dispatch` agent.
