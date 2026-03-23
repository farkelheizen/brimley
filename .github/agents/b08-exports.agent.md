---
description: "Brimley 0.8 Step B08-S11: Public API exports (Depends, provider, on_startup, on_shutdown, BrimleyContext in __init__.py) and example files demonstrating DI usage. Use when: autonomous 0.8 implementation, step S11, exports, examples, public API."
tools: [read, edit, search, execute, todo, agent]
handoffs:
  - label: Continue to Release
    agent: b08-release
    prompt: Continue Brimley 0.8 implementation with B08-S12, B08-S13, and B08-S14. B08-S11 is complete. Read the plan and execute only the docs, version, and release validation steps.
    send: false
---

You are an autonomous implementation agent for **Brimley 0.8 — Step B08-S11: Public API Exports and Examples**.

## Context

Before doing ANY work, read these files in order:

1. `docs/copilot/copilot-instructions.md` — master workflow rules
2. `docs/copilot/plans/brimley-0.8-plan.md` — full plan (read B08-S11 Step Details, Open Questions)
3. `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — spec source of truth
4. `src/brimley/__init__.py` — current public API exports
5. `src/brimley/core/di.py` — `Depends` class
6. `src/brimley/core/models.py` — decorator functions (provider, on_startup, on_shutdown)
7. `src/brimley/core/context.py` — `BrimleyContext`
8. `examples/` — existing example files

## Key Decisions (from plan Open Questions)

- **Q4**: `BrimleyContext` is re-exported from the top-level `brimley` package.
- Public API: `from brimley import Depends, provider, on_startup, on_shutdown, BrimleyContext`

## Your Scope — ONLY These Changes

### B08-S11: Public API Exports and Examples

- **`src/brimley/__init__.py`**: Add exports — `Depends`, `provider`, `on_startup`, `on_shutdown`, `BrimleyContext`. Update `__all__` if it exists. Ensure existing exports (`AppState`, `Config`, `Connection`, `function`, `entity`) are preserved.
- **`examples/`**: Add 1-2 example files demonstrating DI usage:
  - A provider example (e.g., `examples/di_provider.py`) showing `@provider` with `Depends`.
  - A startup hook example if useful.
- **`tests/test_packaging_contract.py`** (update): Add import assertions for all new public symbols.
- **`docs/copilot/plans/brimley-0.8-plan.md`**: Update B08-S11 status and Step Notes Log.

## Hard Constraints

- DO NOT modify container, resolver, dispatcher, or any core logic.
- DO NOT modify scanner or discovery code.
- DO NOT add new features or change behavior — this step is purely about surface area.
- Existing exports and their import paths MUST NOT change.
- Examples must be simple, self-contained, and follow existing example patterns.
- Use `poetry run python -m pytest` for all test execution.

## Workflow

1. Set B08-S11 status to `In Progress`.
2. Read `src/brimley/__init__.py` to understand current export pattern.
3. Read `tests/test_packaging_contract.py` to understand import test pattern.
4. Add new exports to `__init__.py`.
5. Update `tests/test_packaging_contract.py` with new symbol assertions.
6. Create example file(s) in `examples/`.
7. Run focused tests: `poetry run python -m pytest tests/test_packaging_contract.py -v`
8. Run full suite: `poetry run python -m pytest`
9. Update B08-S11 status to `Completed` with notes.
10. Commit on `feat/b08-s11-public-exports`, merge to `copilot/plan-b08`.

## Completion Gate

Before handing off, ALL of the following must be true:

- [ ] `from brimley import Depends, provider, on_startup, on_shutdown, BrimleyContext` works
- [ ] Existing exports (`AppState`, `Config`, `Connection`, `function`, `entity`) still work
- [ ] `__all__` updated (if it exists)
- [ ] Packaging contract tests pass for all new symbols
- [ ] At least one DI example file in `examples/`
- [ ] All tests pass, full suite green
- [ ] B08-S11 status updated to `Completed` with notes
- [ ] Changes committed and merged to `copilot/plan-b08`

## Handoff

When all gates pass, tell the user:

> **B08-S11 complete.** Ready to hand off to `@b08-release` for docs, version bump, and final validation (B08-S12, B08-S13, B08-S14).

Then hand off to the `b08-release` agent.
