# CLI Version Command Plan

> Date: 3/26/2026
> Owner: Copilot
> Branch: feat/cli-version-command
> Related docs: docs/brimley-cli-and-repl-harness.md

This file is a working implementation plan.

## Problem Summary
Brimley CLI has no way to display its installed version. Users can't run `brimley version` or `brimley --version` to check which release is installed.

## Goal
Add a `version` command to the Brimley CLI that prints the installed package version to stdout.

## Scope
- In scope: `brimley version` command, tests, CHANGELOG entry, CLI doc update
- Out of scope: `--version` global flag (Typer callback pattern), version checks against PyPI

## Constraints / Requirements
- Use `brimley.__version__` (already derived from `importlib.metadata`).
- Output only the version string to stdout (pipe-friendly).
- Follow existing CLI patterns (Typer `@app.command()`).

---

## Implementation Plan

| Step ID | Status | Goal | Planned Changes | Test Coverage |
|---|---|---|---|---|
| VER-S1 | Completed | Add test for `version` command | `tests/test_cli.py` | `test_version_command_prints_version` |
| VER-S2 | Completed | Implement `version` command | `src/brimley/cli/main.py` | Same test from VER-S1 |
| VER-S3 | Completed | Update CHANGELOG and CLI doc | `CHANGELOG.md`, `docs/brimley-cli-and-repl-harness.md` | N/A |

---

## Step Details

### VER-S1 Add test for `version` command
**Files (expected):**
- `tests/test_cli.py`

**Implementation notes:**
- Add `test_version_command_prints_version` that invokes `["version"]` and asserts exit code 0 and version string in stdout.

**Definition of done:**
- Test exists and currently fails (command not implemented yet).

### VER-S2 Implement `version` command
**Files (expected):**
- `src/brimley/cli/main.py`

**Implementation notes:**
- Add `@app.command()` for `version` that imports and prints `__version__`.

**Definition of done:**
- `brimley version` prints version string; test from VER-S1 passes.

### VER-S3 Update CHANGELOG and CLI doc
**Files (expected):**
- `CHANGELOG.md`
- `docs/brimley-cli-and-repl-harness.md`

**Implementation notes:**
- Add entry under `[Unreleased]` or next version `Added` section.
- Add `version` to CLI commands list in harness doc.

**Definition of done:**
- Docs reflect the new command.

---

## Acceptance Criteria
- `brimley version` prints the installed version and exits 0.
- Output is clean (version string only, no extra text), pipe-friendly.
- All existing tests still pass.
- `CHANGELOG.md` updated.
- CLI doc updated.

## Risks / Notes
- Minimal risk; isolated additive change.

## Validation Plan
Run tests in this order:
1. Focused: `poetry run pytest tests/test_cli.py::test_version_command_prints_version -v`
2. Full suite: `poetry run pytest`

Record results:
- Focused: 1 passed (0.25s)
- Full suite: 815 passed (7.39s)

---

## Step Notes Log (update as work progresses)

### VER-S1 Notes
- Changes made: Added `test_version_command_prints_version` to `tests/test_cli.py`.
- Deviations: none
- Validation: test passes

### VER-S2 Notes
- Changes made: Added `version` command to `src/brimley/cli/main.py` using `@app.command()`.
- Deviations: none
- Validation: focused test passes; full suite 815 passed

### VER-S3 Notes
- Changes made: Added `[Unreleased]` entry in `CHANGELOG.md`; added `version` command to CLI harness doc.
- Deviations: none
- Validation: N/A (docs only)

---

## Copilot Execution Protocol
When Copilot uses this plan:
1. Set current step to `In Progress` before coding.
2. Implement only the current step scope.
3. Run listed tests for the step.
4. Update step status to `Completed` (or `Blocked`) with notes.
5. Continue to next step only after validation is recorded.
