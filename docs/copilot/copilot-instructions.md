# Copilot Instructions for Brimley

Copilot is being used to assist in building the Brimley engine. To ensure quality and maintainability, you must strictly adhere to the following workflow rules.

## 0. Poetry Project Requirement

This repository is a **Poetry-managed Python project**.

- Use Poetry commands for all environment, run, and test actions.
- Prefer `poetry run ...` for all tooling (tests, CLI, scripts).
- Do not use bare `pytest` or bare `python` unless explicitly requested.
- Install/update dependencies via Poetry (`poetry install`, `poetry add`, `poetry update`).

## 1. Documentation First

- **Current Plan Pointer (Read Before Coding):** Open `docs/copilot/current-plan.md` to identify the active plan document and current step.

- **Docs Routing Map (Start Here):** Always open `docs/copilot/copilot-docs-reference.md` first to quickly route to the correct spec(s) for the task.

- **Architecture Decision Records:** Significant architectural and roadmap decisions are recorded in `docs/decisions/`. Before implementing a feature that touches the roadmap order, runner types, secrets handling, or plugin architecture, check whether a relevant ADR exists. See `docs/decisions/README.md` for the full index.

- **Plan Template:** Use `docs/copilot/copilot-plan-template.md` for all new plans.

- **Plan Doc:** This will be a markdown file under `docs` and must follow the template sections exactly (Problem Summary, Goal, Scope, Constraints, Implementation Plan table, Step Details, Acceptance Criteria, Risks/Notes, Validation Plan, Step Notes Log, Copilot Execution Protocol).
    
- **Specs:** Use the detailed markdown specs under `docs` as the source of truth for logic.

## 2. Step-by-Step Execution

- **Do NOT** attempt to write the entire application at once.

- Set the active step status to `In Progress` before coding.
    
- Identify the **Current Step** in Plan Doc (e.g., `P1-S1`).
    
- Only write code relevant to that specific step.
    
- If a step implies changes to multiple files, that is acceptable, but keep the scope limited to the step's goal.

- Allowed step statuses are: `Not Started` | `In Progress` | `Completed` | `Blocked`.
    

## 3. The "Test-First" Mandate

- For every step involving logic (Classes, Parsers, Runners), you **MUST** write or update a corresponding test file in `tests/` _before_ or _simultaneously_ with the implementation.
    
- **Constraint:** You are not allowed to mark a step as `Completed` until the tests for that step pass and validation is recorded in the Step Notes Log.
    

## 4. Status Tracking & Logging

- After completing a step, you must update Plan Doc:
    - Change Status from `In Progress` to `Completed` (or `Blocked` if unresolved).
    - Update both:
      - the `Implementation Plan` table row
      - the matching entry in `Step Notes Log` (changes made, deviations, validation)

- If you skip a step or deviate from plan scope, record it explicitly in `Step Notes Log` under Deviations.
    

## 5. Review & Commit Protocol

**Mandatory gate:** Once a step is marked `Completed`, required validation has passed, and review approval is given, changes for that step must be committed on an appropriately named branch before proceeding.

- **Before Presenting:**
    1. Run focused tests for the current step (`poetry run pytest <focused tests>`).
    2. Run adjacent/regression tests (`poetry run pytest <adjacent tests>`), when applicable.
    3. Run the full test suite (`poetry run pytest`).
    4. Record results in the plan `Validation Plan` / `Step Notes Log`.
    5. Only if tests pass, present the work for review.
        
- **Review:**
    
    - Ask for my approval to commit.
    
    - Do **NOT** commit without explicit permission.

- **Commit:**

    - Upon approval, checkout a new branch following the pattern `feat/step-name` or `fix/issue-name`.
    
    - Commit the changes with a descriptive message including the step ID (e.g., `feat: Implement Context (P1-S3)`).

    - When creating a GitHub PR, always write the PR body to a temp file (e.g., `/tmp/brimley-pr-body.md`) and pass it via `--body-file`. Never pass a multi-line body inline on the command line.

- **Next Step:**

    - After the commit is complete, ask if I want to proceed to the next step in the plan.
    

## 6. Coding Standards

- Use `pydantic` for all data models.
    
- Use `pathlib` for file handling.
    
- Type hint everything.
    
- Include docstrings for public methods.

## 7. CHANGELOG & Examples Gate

Every plan that introduces a user-visible feature, API change, or bug fix **must** include steps (or at minimum acceptance criteria items) for:

- **`CHANGELOG.md`** — Add entries under the appropriate version heading (`Added`, `Changed`, `Fixed`, `Removed`). Do this as part of the final step or as a dedicated step before the commit gate.
- **`examples/`** — Update any affected example files, CLI invocations, or `brimley.yaml` to reflect the change. Bump the version header in `examples/README.md`. If a new feature has no existing example, consider adding one.

These are **blocking** for the Review & Commit Protocol — a step cannot be marked `Completed` if either item is applicable and not done.

## 8. Doc Scan Gate

When merging or completing a version release, scan **all documents** in `docs/` and the root `README.md` for content that needs updating. This is a required step before the commit gate for any version release plan.

**Step 1 — Release metadata bump (always):**

- `pyproject.toml` — update package version.
- `CHANGELOG.md` — add release notes under `Added`, `Changed`, `Fixed`, and `Removed`.
- `examples/README.md` — update only when examples, CLI invocations, or sample configuration behavior changed.

**Step 2 — Documentation versioning policy (targeted updates, not blanket rewrites):**

- Do **not** mass-update per-doc banner lines solely for patch/minor bumps.
- Prefer stable spec banners where needed, e.g. `Docs baseline: 0.6.x` or `API baseline: 0.6.x`.
- Keep exact release numbers in release metadata (`pyproject.toml`, `CHANGELOG.md`, release notes/tags), not in every spec header.
- Keep version qualifiers in body text only when semantically meaningful (e.g., `Introduced in 0.6+`, `Changed in 0.7`).
- For patch releases (`X.Y.Z`): update only docs directly affected by the bugfix/behavior change.
- For minor releases (`X.Y.0`): update docs affected by behavior/interface/config changes; avoid no-op edits in unrelated docs.

**Step 3 — Targeted content scan:**

- **Stale version references in body text** — e.g., "In Brimley 0.5, ..." — update or rephrase where the feature is now current.
- **Reference Documentation Maps** — Check `docs/brimley-high-level-design.md` §5 and `README.md` Documentation Map for missing or outdated links to new/changed docs.
- **Copilot Docs Reference Map** — `docs/copilot/copilot-docs-reference.md`: add any new topic rows or keyword index entries for new architectural areas.
- **Feature mentions** — If a new architectural area was introduced (e.g., logging, entities, MCP), check that `brimley-high-level-design.md` §3 includes a corresponding Key Component entry.
- **Context doc** — If the context object gained new fields (properties), update `docs/brimley-context.md` table and field detail list.
- **CLI/REPL harness doc** — If new CLI flags or REPL commands were added, update `docs/brimley-cli-and-repl-harness.md` and `docs/brimley-repl-admin-commands.md`.
- **Configuration doc** — If new `brimley.yaml` keys were added, verify `docs/brimley-configuration.md` reflects them.

**This gate is blocking** — a version release plan step cannot be marked `Completed` until release metadata and behaviorally affected docs are updated.

## 9. Plan Completeness Gate

Before starting implementation, verify the active plan includes:

- `Problem Summary`
- `Goal`
- `Scope` (in/out)
- `Constraints / Requirements`
- `Implementation Plan` table with Step IDs and Test Coverage
- `Step Details` for each active step
- `Acceptance Criteria`
- `Risks / Notes`
- `Validation Plan`
- `Step Notes Log`

If any section is missing, update the plan first, then implement.