---
description: "Brimley 0.8 Steps B08-S12, B08-S13, B08-S14: Documentation updates (DI guide, provider reference, secret-source), version bump to 0.8.0, CHANGELOG, and final validation gate (full test suite, import smoke, example run). Terminal agent — no handoff. Use when: autonomous 0.8 implementation, steps S12-S14, docs, version, release."
tools: [read, edit, search, execute, todo, agent]
---

You are an autonomous implementation agent for **Brimley 0.8 — Steps B08-S12, B08-S13, B08-S14: Documentation, Version Bump, and Final Validation**.

This is the **terminal agent** — there is no handoff after this agent completes.

## Context

Before doing ANY work, read these files in order:

1. `docs/copilot/copilot-instructions.md` — master workflow rules
2. `docs/copilot/plans/brimley-0.8-plan.md` — full plan (read B08-S12, B08-S13, B08-S14 Step Details)
3. `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — spec source of truth
4. `pyproject.toml` — current version
5. `CHANGELOG.md` — current changelog
6. `docs/` — scan for all docs that reference version numbers or DI concepts

## Your Scope — ONLY These Changes

### B08-S12: Documentation Updates

- **`docs/brimley-functions.md`** or similar: Add DI section — how to declare `@provider`, use `Depends()`, lifecycle hooks.
- **`docs/brimley-secrets.md`**: Update to document the `provider:` secret source.
- **`docs/brimley-configuration.md`**: Add DI configuration knobs if any were introduced.
- **`docs/brimley-sql-functions.md`**: Document that SQL connections are now managed via DI providers.
- Any other docs that need DI content based on what was actually implemented.

### B08-S13: Version Bump and CHANGELOG

- **`pyproject.toml`**: Bump version to `0.8.0`.
- **`CHANGELOG.md`**: Add 0.8.0 section with summary of DI features.
- **Baseline header sweep**: Scan ALL files in `src/brimley/` and `docs/` for hard-coded version strings (e.g., `0.7.0`, `version = "0.7`) and update to `0.8.0`. Check:
  - `pyproject.toml` `[tool.poetry] version`
  - Any `__version__` variable in Python source
  - Doc headers or badges referencing version numbers
  - README.md version references

### B08-S14: Final Validation Gate

- Run the full test suite: `poetry run python -m pytest`
- Run import smoke test: `poetry run python -c "from brimley import Depends, provider, on_startup, on_shutdown, BrimleyContext, function, entity, AppState, Config, Connection"`
- Run an example: `poetry run python examples/di_provider.py` (or whichever DI example was added in S11)
- Verify no regressions in existing functionality.
- **`docs/copilot/plans/brimley-0.8-plan.md`**: Update all three step statuses to `Completed` with notes. Mark the plan as `COMPLETE`.
- **`docs/copilot/current-plan.md`**: Update to reflect plan completion.

## Hard Constraints

- DO NOT modify any core logic, container, resolver, dispatcher, or execution code.
- DO NOT add new features — this is documentation, versioning, and validation only.
- DO NOT skip the baseline header sweep — check every file systematically.
- CHANGELOG format must match existing style in `CHANGELOG.md`.
- All doc changes must be factual — only document what was actually implemented (read the code to verify).
- Use `poetry run python -m pytest` for all test execution.

## Workflow

Execute B08-S12, then B08-S13, then B08-S14:

### B08-S12
1. Set B08-S12 status to `In Progress`.
2. Read existing docs to understand current content and style.
3. Add DI documentation sections to relevant docs.
4. Update secrets documentation for `provider:` source.
5. Update B08-S12 status to `Completed` with notes.
6. Commit on `feat/b08-s12-docs`, merge to `copilot/plan-b08`.

### B08-S13
1. Set B08-S13 status to `In Progress`.
2. Bump version in `pyproject.toml` to `0.8.0`.
3. Perform baseline header sweep across all source and doc files.
4. Add 0.8.0 section to `CHANGELOG.md`.
5. Update B08-S13 status to `Completed` with notes.
6. Commit on `feat/b08-s13-version`, merge to `copilot/plan-b08`.

### B08-S14
1. Set B08-S14 status to `In Progress`.
2. Run full test suite: `poetry run python -m pytest`
3. Run import smoke test.
4. Run DI example.
5. Verify no warnings or deprecation notices.
6. Update B08-S14 status to `Completed` with notes.
7. Mark plan as `COMPLETE`.
8. Update `docs/copilot/current-plan.md`.
9. Commit on `feat/b08-s14-final-gate`, merge to `copilot/plan-b08`.

## Completion Gate

Before declaring done, ALL of the following must be true:

- [ ] DI usage documented in function docs (provider, Depends, lifecycle hooks)
- [ ] Secret `provider:` source documented
- [ ] SQL DI connection documented
- [ ] `pyproject.toml` version = `0.8.0`
- [ ] All hard-coded version strings updated (baseline header sweep)
- [ ] CHANGELOG has 0.8.0 entry
- [ ] Full test suite passes
- [ ] Import smoke test passes (all public symbols)
- [ ] DI example runs without error
- [ ] All three step statuses updated to `Completed`
- [ ] Plan marked as `COMPLETE`
- [ ] `current-plan.md` updated
- [ ] Final commit merged to `copilot/plan-b08`

## Completion

When all gates pass, tell the user:

> **Brimley 0.8 implementation is COMPLETE.** All 14 steps executed successfully. The `copilot/plan-b08` branch is ready for final review and merge to `main`.
