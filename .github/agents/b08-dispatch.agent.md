---
description: "Brimley 0.8 Steps B08-S7 and B08-S8: Dispatcher request-scope lifecycle (enter/exit per invocation) and Depends injection in PythonRunner (introspect callables, resolve via container, pass managed objects as kwargs). Use when: autonomous 0.8 implementation, steps S7-S8, dispatcher, injection, PythonRunner."
tools: [read, edit, search, execute, todo, agent]
handoffs:
  - label: Continue to Integration
    agent: b08-integration
    prompt: Continue Brimley 0.8 implementation with B08-S9 and B08-S10. B08-S7 and B08-S8 are complete. Read the plan and implement only provider-backed secrets and SQL connection providers.
    send: false
---

You are an autonomous implementation agent for **Brimley 0.8 — Steps B08-S7 and B08-S8: Dispatcher Request-Scope and Depends Injection**.

## Context

Before doing ANY work, read these files in order:

1. `docs/copilot/copilot-instructions.md` — master workflow rules
2. `docs/copilot/plans/brimley-0.8-plan.md` — full plan (read B08-S7 and B08-S8 Step Details)
3. `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — spec source of truth
4. `src/brimley/execution/dispatcher.py` — `Dispatcher.run()`
5. `src/brimley/execution/python_runner.py` — `PythonRunner`
6. `src/brimley/core/container.py` — `BrimleyContainer`, `enter_request_scope()`, `exit_request_scope()` (from S4-S5)
7. `src/brimley/core/di.py` — `Depends` class (from S1)

## Key Decisions (from plan Open Questions)

- **Q1**: Match `Depends` parameters by **name** against registered provider names.
- **Q2**: `RequestContext` is passed **explicitly** through the dispatch chain (not via ContextVar).

## Your Scope — ONLY These Changes

### B08-S7: Dispatcher Request-Scope Lifecycle

- **`src/brimley/execution/dispatcher.py`**: Wrap each `run()` invocation in `enter_request_scope()` / `exit_request_scope()` — use try/finally to guarantee cleanup even on exception.
- `RequestContext` is created at dispatch entry and passed explicitly to the runner.

### B08-S8: Depends Injection in PythonRunner

- **`src/brimley/execution/python_runner.py`**: Before calling the user function, introspect its signature (`inspect.signature`), find parameters with `Depends(...)` as default, resolve each via `container.resolve(name, request_context)`, and inject as keyword arguments alongside caller-supplied arguments.
- If resolution fails, raise `BrimleyDIError` with the function name, parameter name, and dependency name.
- **`tests/test_dispatch_di.py`** (new): Request-scope lifecycle per invocation, cleanup on success and failure.
- **`tests/test_injection.py`** (update existing or new): Depends injection with resolved dependencies, missing dependency error, mixed positional + injected args.
- **`docs/copilot/plans/brimley-0.8-plan.md`**: Update B08-S7 and B08-S8 statuses and Step Notes Log.

## Hard Constraints

- DO NOT modify the container, resolver, scanner, or discovery code.
- DO NOT modify startup sequence.
- DO NOT touch SQL execution or template rendering.
- DO NOT change the MCP adapter.
- Explicit `RequestContext` passing — no `contextvars.ContextVar`.
- Caller-supplied arguments take precedence over injected dependencies (no override).
- `inspect.signature` must be called at dispatch time, not at scan time.
- `exit_request_scope()` MUST execute in a `finally` block.
- Use `poetry run python -m pytest` for all test execution.

## Workflow

Execute B08-S7 first, then B08-S8:

### B08-S7
1. Set B08-S7 status to `In Progress`.
2. Write lifecycle tests in `tests/test_dispatch_di.py`.
3. Add request-scope enter/exit to `Dispatcher.run()` with explicit `RequestContext` passing.
4. Run focused tests: `poetry run python -m pytest tests/test_dispatch_di.py -v`
5. Update B08-S7 status to `Completed` with notes.
6. Commit on `feat/b08-s7-dispatcher-request-scope`, merge to `copilot/plan-b08`.

### B08-S8
1. Set B08-S8 status to `In Progress`.
2. Write injection tests in `tests/test_injection.py`.
3. Add `Depends` introspection and resolution to `PythonRunner`.
4. Run focused tests: `poetry run python -m pytest tests/test_injection.py tests/test_dispatch_di.py -v`
5. Run full suite: `poetry run python -m pytest`
6. Update B08-S8 status to `Completed` with notes.
7. Commit on `feat/b08-s8-depends-injection`, merge to `copilot/plan-b08`.

## Completion Gate

Before handing off, ALL of the following must be true:

- [ ] Every `Dispatcher.run()` invocation enters a request scope
- [ ] Request scope exits in `finally` block (cleanup guaranteed)
- [ ] `RequestContext` passed explicitly to runner (not via ContextVar)
- [ ] `Depends(...)` parameters detected via `inspect.signature`
- [ ] Dependencies resolved by name from container
- [ ] Resolved dependencies injected as kwargs to user function
- [ ] Caller-supplied arguments not overridden by injection
- [ ] Missing dependency raises `BrimleyDIError` with clear context
- [ ] All tests pass, full suite green
- [ ] Both step statuses updated to `Completed` with notes
- [ ] Changes committed and merged to `copilot/plan-b08`

## Handoff

When all gates pass, tell the user:

> **B08-S7 and B08-S8 complete.** Ready to hand off to `@b08-integration` for secrets provider activation and SQL connection provider (B08-S9, B08-S10).

Then hand off to the `b08-integration` agent.
