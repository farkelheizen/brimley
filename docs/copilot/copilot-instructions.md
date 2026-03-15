# Copilot Instructions for Brimley

I am using you to build the Brimley engine. To ensure quality and maintainability, you must strictly adhere to the following workflow rules.

DO NOT attempt to commit any files inside the `.github` directory or the `docs_local` directory. These files are for documentation and instructions only. If you need to create a new instruction file, place it in `.docs_local` directory and follow the existing format.

## 0. Poetry Project Requirement

This repository is a **Poetry-managed Python project**.

- Use Poetry commands for all environment, run, and test actions.
- Prefer `poetry run ...` for all tooling (tests, CLI, scripts).
- Do not use bare `pytest` or bare `python` unless explicitly requested.
- Install/update dependencies via Poetry (`poetry install`, `poetry add`, `poetry update`).

## 1. Documentation First

- **Current Plan Pointer (Read Before Coding):** Open `docs_local/copilot/current-plan.md` to identify the active plan document and current step.

- **Docs Routing Map (Start Here):** Always open `docs_local/copilot/copilot-docs-reference.md` first to quickly route to the correct spec(s) for the task.

- **Plan Template:** Use `docs_local/copilot/copilot-plan-template.md` for all new plans.

- **Plan Doc:** This will be a markdown file under `docs_local` and must follow the template sections exactly (Problem Summary, Goal, Scope, Constraints, Implementation Plan table, Step Details, Acceptance Criteria, Risks/Notes, Validation Plan, Step Notes Log, Copilot Execution Protocol).
    
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

- **Next Step:**

    - After the commit is complete, ask if I want to proceed to the next step in the plan.
    

## 6. Coding Standards

- Use `pydantic` for all data models.
    
- Use `pathlib` for file handling.
    
- Type hint everything.
    
- Include docstrings for public methods.

## 7. Plan Completeness Gate

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