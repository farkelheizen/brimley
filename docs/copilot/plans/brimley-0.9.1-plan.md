# 20260415-brimley-0.9.1 Plan: Optional Oracle Example and Documentation Alignment

> Date: 4/15/2026
> Owner: Copilot
> Branch: feat/brimley-0.9.1-oracle-docs
> Related docs: `README.md`, `docs/brimley-configuration.md`, `docs/brimley-sql-execution.md`, `docs/brimley-project-structure.md`, `docs/brimley-high-level-design.md`, `CHANGELOG.md`, `examples/README.md`

This file is intended as a working implementation plan.

## Problem Summary
Brimley's SQL runner already uses SQLAlchemy engines, so Oracle connectivity fits the existing execution model. However, the repository needs a cleaner release boundary for Oracle support: the Oracle driver must remain optional, the default installation path must not imply Oracle is required, and any Oracle-specific examples must not become part of the baseline getting-started flow.

The current repository also needs a small release-alignment pass for `0.9.1`. Package metadata remains at `0.9.0`, and the newly added Oracle guidance should be organized so the main docs stay accurate for the baseline product while clearly pointing advanced users to an optional Oracle path.

## Goal
Ship `0.9.1` as a patch release that keeps Oracle support fully optional, adds an isolated optional Oracle example with Docker-based startup instructions and a partitioned Brimley app subdirectory, and aligns release metadata and documentation with the new release.

## Scope
- In scope: keep Oracle as an optional dependency extra; isolate Oracle-specific example assets and setup instructions from the baseline examples; partition the Oracle example so Brimley-scannable assets live under an app-specific subdirectory; add Docker instructions for a free local Oracle instance; update release metadata and targeted docs for `0.9.1`
- Out of scope: mandatory Oracle support in the default install path; Oracle thick-mode/client-library automation; CI integration tests that require Docker or a running Oracle instance; replacing `examples/` or repurposing `examples2/` for Oracle

## Constraints / Requirements
- `poetry install` must remain sufficient for the baseline product and must not install Oracle drivers.
- Oracle support must be opt-in via an explicit extra (for example `poetry install -E oracle`) and opt-in example documentation.
- No default validation path, test run, or documentation quickstart may require Oracle, Docker, or Oracle client libraries.
- Oracle example assets must be clearly separated from the baseline `examples/` flow so new users are not steered into optional infrastructure.
- Within the Oracle example workspace, Brimley application assets must live under a dedicated subdirectory (recommended: `oracle_examples/app/`) so Docker Compose files, env files, and support artifacts are outside the main scanner target.
- Oracle example commands should assume the developer is working from within `oracle_examples/` and should use `--root ./app` when invoking Brimley from that directory.
- Docker guidance should prefer Oracle's published Oracle Free image (`container-registry.oracle.com/database/free:latest`) as the safest default from a provenance standpoint, and should clearly state the registry-login requirement, credentials, and port assumptions.
- Docs must use American English spelling and follow the targeted doc-scan policy rather than blanket version churn.
- Existing SQLAlchemy-based SQL runner behavior and current database initialization tests must remain intact.

---

## Implementation Plan

| Step ID | Status | Goal | Planned Changes | Test Coverage |
|---|---|---|---|---|
| B091-S1 | Completed | Lock the optional Oracle boundary | Audit and normalize package/docs language so Oracle remains an optional extra; clarify baseline vs optional install paths in `pyproject.toml`, `README.md`, and SQL/config docs | `tests/test_database_init.py`; `poetry check` |
| B091-S2 | Completed | Add an isolated Oracle example project | Create a separate optional Oracle example workspace (recommended: `oracle_examples/`) with a partitioned `app/` subtree for Brimley assets, plus env template and Docker startup instructions for Oracle Free | Optional smoke instructions only; no required CI runtime Oracle test |
| B091-S3 | Completed | Integrate the Oracle example into project docs without polluting the baseline path | Update top-level docs and example indexes to point to the optional Oracle example, explain when to use it, and keep baseline examples SQLite-first | `poetry run pytest tests/test_config_loader.py tests/test_context_config.py -v` |
| B091-S4 | Not Started | Align release metadata and targeted docs for 0.9.1 | Bump `pyproject.toml` to `0.9.1`, update `CHANGELOG.md`, scan targeted docs/reference maps, and update any affected example/version markers | `poetry run pytest tests/test_database_init.py tests/test_config_loader.py tests/test_context_config.py -v`; `poetry check` |
| B091-S5 | Not Started | Final validation and release gate | Run focused/regression/full validation, confirm no Oracle dependency is pulled into the baseline install path, and record results in plan notes | `poetry run pytest`; optional manual doc/example review |

Status values: `Not Started` | `In Progress` | `Completed` | `Blocked`

---

## Step Details

### B091-S1 Lock the optional Oracle boundary
**Files (expected):**
- `pyproject.toml`
- `poetry.lock`
- `README.md`
- `docs/brimley-configuration.md`
- `docs/brimley-sql-execution.md`

**Implementation notes:**
- Keep the Oracle driver behind an optional dependency extra only.
- Make the baseline install/docs language explicit: Oracle is supported, but not required.
- Ensure database config documentation distinguishes baseline SQL support from Oracle-specific setup.

**Definition of done:**
- Base installation instructions remain Oracle-free.
- Oracle installation is clearly opt-in.
- No existing test/documented path implies Oracle is required for baseline use.

### B091-S2 Add an isolated Oracle example project
**Files (expected):**
- `oracle_examples/README.md`
- `oracle_examples/.env.example`
- `oracle_examples/compose.yaml` or `oracle_examples/docker-compose.yaml`
- `oracle_examples/app/brimley.yaml`
- `oracle_examples/app/*.sql`
- optional `oracle_examples/app/*.py` or `oracle_examples/app/*.md` assets if the example benefits from them
- optional helper scripts only if they reduce setup friction without adding mandatory runtime dependencies

**Implementation notes:**
- Recommended approach: create a separate `oracle_examples/` project instead of modifying baseline `examples/` or overloading `examples2/`.
- Place Brimley application assets under `oracle_examples/app/` and assume the developer runs commands from within `oracle_examples/`, using `--root ./app`, so the scanner does not waste time on Docker YAML, `.env` files, or other support assets at the workspace root.
- Prefer Oracle's published Oracle Free image, `container-registry.oracle.com/database/free:latest`, for the documented Docker flow. Document the Oracle Container Registry login prerequisite explicitly. If later we decide the login friction is too high, the fallback candidate is `gvenzl/oracle-free:latest`, but that is not the default plan.
- Keep the example self-contained and clearly marked optional.
- Avoid adding tests that require Docker or a running Oracle instance in normal CI.

**Definition of done:**
- A user can follow the example README to start a local Oracle instance in Docker, install the Oracle extra, and point Brimley SQL tools at a pooled Oracle connection.
- The Oracle example demonstrates the partitioned layout clearly enough that users can copy it for their own projects.
- The example is isolated enough that baseline users never need to interact with it.

### B091-S3 Integrate the Oracle example into project docs without polluting the baseline path
**Files (expected):**
- `README.md`
- `examples/README.md`
- `docs/brimley-project-structure.md`
- `docs/brimley-high-level-design.md`
- `docs/copilot/copilot-docs-reference.md` (if navigation keywords change)

**Implementation notes:**
- Keep the main quickstart focused on the baseline install and core examples.
- Add concise pointers to the optional Oracle example rather than duplicating Oracle setup across multiple docs.
- If a new example directory is added, update project-structure/reference docs only where the new directory is materially useful to readers.

**Definition of done:**
- The documentation clearly separates baseline examples from optional Oracle-specific examples.
- Readers can find the Oracle example without mistaking it for a required setup step.

### B091-S4 Align release metadata and targeted docs for 0.9.1
**Files (expected):**
- `pyproject.toml`
- `CHANGELOG.md`
- affected docs under `docs/`
- affected example docs under `examples/` and optional Oracle example docs

**Implementation notes:**
- Bump the package version to `0.9.1`.
- Add `Added` / `Changed` / `Fixed` entries reflecting optional Oracle support boundaries, the isolated example, and any documentation corrections.
- Follow the repository's targeted doc-scan rule: update only docs meaningfully affected by the `0.9.1` changes and release metadata.

**Definition of done:**
- Release metadata reflects `0.9.1`.
- Targeted docs match the new release content and navigation.
- Changelog entries explain the release clearly.

### B091-S5 Final validation and release gate
**Files (expected):**
- `docs/copilot/plans/brimley-0.9.1-plan.md`

**Implementation notes:**
- Validate that focused tests pass and baseline metadata remains healthy.
- Run the full suite before presenting the release work.
- Record exactly what was and was not validated for the optional Oracle example path.

**Definition of done:**
- Validation results are recorded in this plan.
- Any remaining Oracle runtime gaps are explicitly documented before review.

---

## Acceptance Criteria
- Oracle support remains fully optional and does not alter the baseline install path.
- A separate optional Oracle example exists with Docker instructions for a free local Oracle instance.
- The Oracle example uses a partitioned layout so Brimley scans only the intended app subtree.
- Baseline docs continue to work for users who do not care about Oracle.
- Diagnostics/errors and setup instructions are clear about optional dependencies and assumptions.
- Documentation updated where behavior changed.
- `CHANGELOG.md` updated with Added / Changed / Fixed entries for this version.
- `examples/` updated only where the baseline example index or cross-links are affected; the optional Oracle example is added separately.
- Version bump performed: `pyproject.toml` updated to `0.9.1`, and targeted docs/release metadata updated where semantically required.
- Doc Scan performed: stale body-text version references updated, reference maps updated if needed, new example-project navigation reflected where relevant.
- **Pre-publish gate:** `pyproject.toml` `version` field must reflect `0.9.1` before running `poetry build` / `poetry publish`.

## Risks / Notes
- The main product risk is user confusion if Oracle setup appears in the default quickstart instead of a clearly optional path.
- Oracle Docker image choice has tradeoffs: official Oracle images may add friction, while community-maintained Oracle Free images may need an explicit trust decision.
- Oracle example validation will likely remain partially manual unless the project chooses to add Docker-backed optional CI.
- A separate example workspace is the cleanest isolation boundary, but it adds one more project surface to maintain.
- The `oracle_examples/app` split improves scan hygiene, but the docs must be explicit about using `--root ./app` when running from inside the example workspace.
- Using Oracle's published image is safer from a provenance standpoint, but it may add registry-auth friction for first-time users.

## Validation Plan
Run tests in this order:
1. Focused tests for changed module(s): `poetry run pytest tests/test_database_init.py -v`
2. Adjacent/regression tests: `poetry run pytest tests/test_config_loader.py tests/test_context_config.py -v`
3. Full suite: `poetry run pytest`

Record results:
- Focused: [pass/fail + summary]
- Regression: [pass/fail + summary]
- Full suite: [pass/fail + summary]

---

## Step Notes Log (update as work progresses)

### B091-S1 Notes
- Changes made: Kept Oracle behind an optional dependency extra, corrected database engine option forwarding, tightened baseline README/config wording so Oracle stays explicitly optional, and moved Oracle config guidance out of the baseline configuration example.
- Deviations: Full-suite validation exposed an unrelated `examples2` regression where `import_jacoco_report` returned a plain dict instead of `ImportReportResult`; restored the declared entity return type so the required full-suite gate could pass.
- Validation: Focused `poetry run pytest tests/test_database_init.py -v` passed (4/4). Regression `poetry run pytest tests/test_config_loader.py tests/test_context_config.py -v` passed (18/18). Full suite `poetry run pytest` passed (987/987, warnings only).

### B091-S2 Notes
- Changes made: Added `oracle_examples/` with Oracle Container Registry Compose startup, shell-driven env template, a partitioned `oracle_examples/app/` Brimley subtree, an `@on_startup` Oracle schema bootstrap hook, and Oracle SQL demo tools. Added unit coverage for the startup bootstrap logic.
- Deviations: none
- Validation: `poetry run pytest tests/test_oracle_example_bootstrap.py -v`; `poetry run pytest tests/test_database_init.py tests/test_config_loader.py tests/test_context_config.py tests/test_oracle_example_bootstrap.py -v`; `poetry run pytest`

### B091-S3 Notes
- Changes made: Linked the new optional Oracle example from the root README and the baseline examples README, while keeping the default examples path explicitly SQLite-first.
- Deviations: none
- Validation: `poetry run pytest tests/test_config_loader.py tests/test_context_config.py -v`; `poetry run pytest`

### B091-S4 Notes
- Changes made: [not started]
- Deviations: [none / description]
- Validation: [not run]

### B091-S5 Notes
- Changes made: [not started]
- Deviations: [none / description]
- Validation: [not run]

---

## Copilot Execution Protocol
When Copilot uses this plan:
1. Set current step to `In Progress` before coding.
2. Implement only the current step scope.
3. Run listed tests for the step.
4. Update step status to `Completed` (or `Blocked`) with notes.
5. Continue to next step only after validation is recorded.