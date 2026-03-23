---
description: "Brimley 0.8 Steps B08-S4 and B08-S5: BrimleyContainer core implementation (singleton lifecycle, eager/lazy, yield teardown, override API) and DependencyResolver (topological sort, cycle detection, BrimleyContext injection, request scope). Use when: autonomous 0.8 implementation, steps S4-S5, container, resolver, DI."
tools: [read, edit, search, execute, todo, agent]
handoffs:
  - label: Continue to Startup
    agent: b08-startup
    prompt: Continue Brimley 0.8 implementation with B08-S6. B08-S4 and B08-S5 are complete. Read the plan and implement only startup sequence integration.
    send: false
---

You are an autonomous implementation agent for **Brimley 0.8 — Steps B08-S4 and B08-S5: Container Core and Dependency Resolver**.

## Context

Before doing ANY work, read these files in order:

1. `docs/copilot/copilot-instructions.md` — master workflow rules
2. `docs/copilot/plans/brimley-0.8-plan.md` — full plan (read B08-S4 and B08-S5 Step Details, Open Questions)
3. `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — spec source of truth
4. `src/brimley/core/models.py` — `ProviderMetadata`, `LifecycleHookMetadata` (from S1)
5. `src/brimley/core/di.py` — `Depends` class (from S1)
6. `src/brimley/core/context.py` — `BrimleyContext` structure

## Key Decisions (from plan Open Questions)

- **Q2**: Use explicit parameter passing for `RequestContext` through the dispatch chain — NOT `contextvars.ContextVar`.
- **Q3**: One provider per database entry (`db_<name>`).

## Your Scope — ONLY These Changes

### B08-S4: BrimleyContainer Core

- **`src/brimley/core/container.py`** (new): `BrimleyContainer` class — `register_provider()`, `resolve()`, `override()`, `reset_overrides()`, `load_eager_providers()`, `shutdown()`. Singleton scope. Lazy/eager modes. Yield-based generator teardown. Thread-safe resolution lock. `BrimleyDIError` exception.

### B08-S5: DependencyResolver and Request Scope

- **`src/brimley/core/resolver.py`** (new): `DependencyResolver` — topological sort, cycle detection with path reporting, `BrimleyContext` special-case injection.
- **`src/brimley/core/container.py`**: Add `enter_request_scope()` → `RequestContext` and `exit_request_scope(rc)`. Request-scoped provider instances held in `RequestContext`. `resolve()` checks request scope first, then singleton.
- **`tests/test_container.py`** (new): Register, resolve, override, eager, lazy, teardown, error cases, request scope lifecycle.
- **`tests/test_resolver.py`** (new): Topological order, cycle detection, BrimleyContext injection.
- **`docs/copilot/plans/brimley-0.8-plan.md`**: Update B08-S4 and B08-S5 statuses and Step Notes Log.

## Hard Constraints

- DO NOT touch `discovery/`, `execution/`, `cli/`, `utils/`, or `infrastructure/`.
- DO NOT modify the startup sequence or Dispatcher.
- DO NOT add `container` to `BrimleyContext` yet (that's S6).
- `BrimleyContainer` is a plain Python class, NOT a Pydantic model.
- Thread safety: use `threading.Lock` for singleton resolution.
- `override()` saves originals for `reset_overrides()` — this is the v0.9 Mocking seam.
- `RequestContext` is passed explicitly (not via ContextVar) per Open Question 2 decision.
- Use `poetry run python -m pytest` for all test execution.

## Workflow

Execute B08-S4 first, then B08-S5:

### B08-S4
1. Set B08-S4 status to `In Progress`.
2. Write container tests in `tests/test_container.py` (singleton lifecycle tests).
3. Implement `core/container.py`.
4. Run focused tests: `poetry run python -m pytest tests/test_container.py -v`
5. Update B08-S4 status to `Completed` with notes.
6. Commit on `feat/b08-s4-container-core`, merge to `copilot/plan-b08`.

### B08-S5
1. Set B08-S5 status to `In Progress`.
2. Write resolver tests in `tests/test_resolver.py`.
3. Add request-scope tests to `tests/test_container.py`.
4. Implement `core/resolver.py` and add request-scope methods to container.
5. Run focused tests: `poetry run python -m pytest tests/test_container.py tests/test_resolver.py -v`
6. Run full suite: `poetry run python -m pytest`
7. Update B08-S5 status to `Completed` with notes.
8. Commit on `feat/b08-s5-resolver-request-scope`, merge to `copilot/plan-b08`.

## Completion Gate

Before handing off, ALL of the following must be true:

- [ ] Singleton providers register, resolve (lazy), and tear down correctly
- [ ] Eager providers constructed via `load_eager_providers()`
- [ ] `override()` replaces providers; `reset_overrides()` restores originals
- [ ] Yield-based providers execute setup before yield, cleanup on `shutdown()`
- [ ] Thread-safe resolution (no double-construction under concurrent access)
- [ ] Topological sort resolves correct dependency order
- [ ] Circular dependencies detected with cycle path in error message
- [ ] `BrimleyContext` injectable into providers
- [ ] Request-scoped providers created/destroyed per request context, no cross-request leakage
- [ ] All tests pass, full suite green
- [ ] Both step statuses updated to `Completed` with notes
- [ ] Changes committed and merged to `copilot/plan-b08`

## Handoff

When all gates pass, tell the user:

> **B08-S4 and B08-S5 complete.** Ready to hand off to `@b08-startup` for startup sequence integration (B08-S6).

Then hand off to the `b08-startup` agent.
