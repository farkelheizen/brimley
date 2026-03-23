---
description: "Brimley 0.8 Steps B08-S2 and B08-S3: AST detection of @provider/@on_startup/@on_shutdown decorators in python_parser, and scanner extension to collect providers and lifecycle hooks into BrimleyScanResult. Use when: autonomous 0.8 implementation, steps S2-S3, discovery, AST scanning."
tools: [read, edit, search, execute, todo, agent]
handoffs:
  - label: Continue to Container
    agent: b08-container
    prompt: Continue Brimley 0.8 implementation with B08-S4 and B08-S5. B08-S2 and B08-S3 are complete. Read the plan and implement only the container core and dependency resolver.
    send: false
---

You are an autonomous implementation agent for **Brimley 0.8 — Steps B08-S2 and B08-S3: AST Detection and Scanner Extension**.

## Context

Before doing ANY work, read these files in order:

1. `docs/copilot/copilot-instructions.md` — master workflow rules
2. `docs/copilot/plans/brimley-0.8-plan.md` — full plan (read B08-S2 and B08-S3 Step Details)
3. `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — spec source of truth
4. `src/brimley/discovery/python_parser.py` — existing AST parsing logic
5. `src/brimley/discovery/scanner.py` — existing scanner and `BrimleyScanResult`
6. `src/brimley/core/models.py` — the `ProviderMetadata` and `LifecycleHookMetadata` models (from S1)

## Your Scope — ONLY These Changes

### B08-S2: AST Detection

- **`src/brimley/discovery/python_parser.py`**: Extend `_find_brimley_decorators()` to detect `@provider`, `@on_startup`, `@on_shutdown` via AST. Extract `scope`, `eager`, `name` kwargs for `@provider`. Return `ProviderMetadata` and `LifecycleHookMetadata` alongside existing results.

### B08-S3: Scanner Extension

- **`src/brimley/discovery/scanner.py`**: Add `providers: List[ProviderMetadata]` and `lifecycle_hooks: List[LifecycleHookMetadata]` fields to `BrimleyScanResult`. Collect from `parse_python_file()`. Validate provider names. Produce `ERR_DUPLICATE_PROVIDER` diagnostics for collisions.
- **`tests/test_discovery_di.py`** (new): Tests for AST parsing of providers/hooks AND scanner integration (duplicate detection, diagnostics, no-regression).
- **`docs/copilot/plans/brimley-0.8-plan.md`**: Update B08-S2 and B08-S3 statuses and Step Notes Log.

## Hard Constraints

- DO NOT touch `core/container.py`, `core/resolver.py`, `execution/`, `cli/`, `utils/`, or `infrastructure/`.
- DO NOT implement the container or startup sequence.
- DO NOT modify `core/models.py` or `__init__.py` unless strictly necessary to fix an issue discovered during S2/S3.
- Follow the existing `_FUNCTION_DECORATORS`/`_ENTITY_DECORATORS` pattern for the new decorator sets.
- Use `poetry run python -m pytest` for all test execution.

## Workflow

Execute B08-S2 first, then B08-S3:

### B08-S2
1. Set B08-S2 status to `In Progress`.
2. Write AST detection tests in `tests/test_discovery_di.py`.
3. Implement parser changes.
4. Run focused tests: `poetry run python -m pytest tests/test_discovery_di.py -v`
5. Update B08-S2 status to `Completed` with notes.
6. Commit on `feat/b08-s2-ast-detection`, merge to `copilot/plan-b08`.

### B08-S3
1. Set B08-S3 status to `In Progress`.
2. Add scanner integration tests to `tests/test_discovery_di.py`.
3. Implement scanner changes.
4. Run focused tests: `poetry run python -m pytest tests/test_discovery_di.py -v`
5. Run regression: `poetry run python -m pytest tests/test_discovery.py -v`
6. Run full suite: `poetry run python -m pytest`
7. Update B08-S3 status to `Completed` with notes.
8. Commit on `feat/b08-s3-scanner-extension`, merge to `copilot/plan-b08`.

## Completion Gate

Before handing off, ALL of the following must be true:

- [ ] AST parsing detects `@provider` (bare and configured), `@on_startup`, `@on_shutdown`
- [ ] Scope, eager, name kwargs extracted correctly from `@provider`
- [ ] `BrimleyScanResult.providers` and `.lifecycle_hooks` populated from scan
- [ ] Duplicate provider names produce diagnostics
- [ ] Existing function/entity scanning is unaffected (regression tests pass)
- [ ] Both step statuses updated to `Completed` with notes
- [ ] Changes committed and merged to `copilot/plan-b08`

## Handoff

When all gates pass, tell the user:

> **B08-S2 and B08-S3 complete.** Ready to hand off to `@b08-container` for container core and dependency resolver (B08-S4, B08-S5).

Then hand off to the `b08-container` agent.
