---
name: brimley-0.7-wave-4
description: Brimley 0.7 Wave 4 — end-to-end examples, canonical documentation, version bump to 0.7.0, doc scan gate, and final validation (B07-S14 through B07-S17).
---

You are implementing Brimley 0.7 per the plan in `docs/copilot/plans/brimley-0.7-plan.md`.

## Autonomy Grant

I grant explicit approval for this run to execute steps B07-S14 through B07-S17 without pausing for additional approval between steps. Operate autonomously in implementation mode. Do not ask for decision-gate confirmation after each step. You are authorized to create multiple commits and push them. Do NOT stop and ask "should I proceed?" between steps.

## Binding Decisions

Use the resolved SD and OQ decisions in the plan as binding. Do not re-open or re-debate resolved questions. If new ambiguity arises, choose the conservative option that preserves tests and security, then log the decision in the Step Notes Log.

## Workflow Per Step

1. Set the step status to `In Progress` in the plan.
2. Implement only that step's scope.
3. Run the listed tests for the step (`poetry run python -m pytest ...`).
4. If tests pass: update step status to `Completed`, record changes/deviations/validation in the Step Notes Log, and commit with the step ID in the message.
5. If tests fail: attempt up to 3 fix iterations. If still failing after 3 attempts, mark the step `Blocked` with the exact failure reason in the Step Notes Log and continue to the next non-dependent step.
6. Do NOT perform destructive git operations (no force push, no `reset --hard`, no deleting branches).

## Commit Conventions

- Branch: continue on `copilot/plan-b07`
- Commit message pattern: `feat(b07-sN): <short description>`
- When creating PR bodies, always write to a temp file and use `--body-file`. Never pass multi-line body inline on the command line.

## Reference Docs

Read these before coding:

- `docs/copilot/copilot-instructions.md` — workflow rules, **including §8 Doc Scan Gate** (required for S16)
- `docs/copilot/copilot-docs-reference.md` — spec routing map (update in S15)
- `docs/copilot/plans/brimley-0.7-plan.md` — source of truth for this release
- `docs/roadmap/brimley-0.7-api-functions.md` — API function spec (SD updates already applied)
- `docs/roadmap/brimley-0.7-cli-functions.md` — CLI function spec (SD updates already applied)

## Progress Reporting

After completing each step, output a brief status line before proceeding to the next:

```
✅ B07-SN: <what was done> | tests: <pass count> passed, <fail count> failed
```

or, if blocked:

```
❌ B07-SN: BLOCKED — <exact reason>
```

---

## Wave 4 Scope: B07-S14 → B07-S15 → B07-S16 → B07-S17

Execute steps B07-S14 through B07-S17 from the plan in order.

### Step order

1. **B07-S14** — Add `examples/github_profile.yaml` (API function example using `env` secret source for `GITHUB_TOKEN`) and `examples/system_metrics.yaml` (CLI function example using `uptime` with `regex` parser). Update `examples/brimley.yaml` if needed. Update `examples/README.md` with new examples and v0.7 version header. Add discovery integration tests in `tests/test_e2e_examples.py`.

2. **B07-S15** — Documentation and operator guidance:
   - Create new canonical spec docs:
     - `docs/brimley-api-functions.md` (derived from roadmap spec, written as canonical)
     - `docs/brimley-cli-functions.md`
     - `docs/brimley-secrets.md` (secrets resolution, two-layer redaction, known gaps, OQ-12 warning-vs-error behavior)
   - Update existing docs to reference new function types: `docs/brimley-functions.md`, `docs/brimley-discovery-and-loader-specification.md`, `docs/brimley-model-context-protocol-integration.md`, `docs/brimley-configuration.md` (add `security:` section for `prompt_injection_screening`), `docs/brimley-high-level-design.md`, `docs/brimley-cli-and-repl-harness.md`, `docs/brimley-diagnostics-and-error-reporting.md`.
   - Update `docs/copilot/copilot-docs-reference.md`: add keyword entries for `api_function`, `cli_function`, `secrets`, `BaseRunner`, `ApiRunner`, `CliRunner`, `SecretsResolver`.
   - Update `README.md` documentation map and feature list.
   - The Specification Deviations section (SD-1 through SD-5) in the plan lists all spec updates required — review each one and confirm it is reflected in the canonical docs.
   - Document that `jinja2.sandbox.SandboxedEnvironment` is used for all template rendering (OQ-9) in the new API and CLI function spec docs.

3. **B07-S16** — Version bump and doc scan gate:
   - Bump `pyproject.toml` version to `0.7.0`.
   - Update `CHANGELOG.md`: Added (ApiFunction, CliFunction, BaseRunner, SecretsResolver, YAML scanner, httpx, security hardening, threat model), Changed (Dispatcher routing, BrimleyFunction secrets field, MCP provider).
   - Run the full doc scan gate per `copilot-instructions.md` §8: check stale version references, confirm reference documentation maps are updated, confirm Copilot docs reference map is complete.

4. **B07-S17** — Final validation and handoff:
   - Run the complete Validation Plan from the plan document (focused, regression, full suite, Bandit).
   - Fill in all checkboxes in the security acceptance gate checklist in the plan.
   - Record all test results in the plan's Validation Plan section.
   - Prepare PR body: write to `/tmp/brimley-0.7-pr-body.md`. Include: summary of all 17 steps, wave outcomes, security gate status, known gaps (provider secrets, MockRegistry, httpx singleton), and breaking-change notes (none expected).

### Final validation commands

```bash
poetry run python -m pytest tests/test_models.py tests/test_secrets.py tests/test_yaml_parser.py tests/test_execution_api.py tests/test_execution_cli.py tests/test_security_cli_injection.py tests/test_security_api_injection.py -q
poetry run python -m pytest tests/test_execution.py tests/test_execution_python.py tests/test_execution_sql.py tests/test_execution_jinja.py tests/test_discovery.py tests/test_mcp_provider.py tests/test_mcp_adapter.py tests/test_e2e_examples.py -q
poetry run python -m pytest
poetry run bandit -r src/brimley -ll
```

---

## Completion — Do NOT proceed further

After B07-S17 is complete:

1. Confirm `/tmp/brimley-0.7-pr-body.md` has been written.
2. Output the final status summary for all 17 steps (B07-S1 through B07-S17).
3. **Stop.** Do NOT create the PR. Do NOT merge. The user will review and merge manually.

The user will create the PR with:

```bash
gh pr create --title "feat: Brimley 0.7.0 — API & CLI Functions" --body-file /tmp/brimley-0.7-pr-body.md --base main
```
