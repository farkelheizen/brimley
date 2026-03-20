---
name: brimley-0.7-wave-3
description: Brimley 0.7 Wave 3 — security hardening: CLI and API injection tests, Bandit/Semgrep/detect-secrets tooling, llm-guard hook, and threat model document (B07-S10 through B07-S13).
---

You are implementing Brimley 0.7 per the plan in `docs/copilot/plans/brimley-0.7-plan.md`.

## Autonomy Grant

I grant explicit approval for this run to execute steps B07-S10 through B07-S13 without pausing for additional approval between steps. Operate autonomously in implementation mode. Do not ask for decision-gate confirmation after each step. You are authorized to create multiple commits and push them. Do NOT stop and ask "should I proceed?" between steps.

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

- `docs/copilot/copilot-instructions.md` — workflow rules
- `docs/copilot/copilot-docs-reference.md` — spec routing map
- `docs/copilot/plans/brimley-0.7-plan.md` — source of truth for this release
- `docs/roadmap/brimley-0.7-api-functions.md` — API function spec
- `docs/roadmap/brimley-0.7-cli-functions.md` — CLI function spec

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

## Wave 3 Scope: B07-S10 → B07-S11 → B07-S12 → B07-S13

Execute steps B07-S10 through B07-S13 from the plan. S10 and S11 have no mutual dependency and may be done in either order. S12 depends on both. S13 (threat model doc) is fully independent.

### Step order

1. **B07-S10** — CLI argument sanitization hardening in `src/brimley/execution/cli_runner.py`: shell metacharacter rejection on post-render `command_arguments` values. Build `tests/test_security_cli_injection.py` with representative payloads (command injection, path traversal, env injection).
2. **B07-S11** — API request sanitization hardening in `src/brimley/execution/api_runner.py`: URL scheme validation (http/https only, reject embedded credentials), header `\r\n` injection prevention, Jinja2 sandbox validation. Build `tests/test_security_api_injection.py`.
3. **B07-S12** — Security tooling integration:
   - **Bandit:** Add `[tool.bandit]` config to `pyproject.toml`. Run `poetry run bandit -r src/brimley -ll` and fix all B602/B603 violations.
   - **Semgrep:** Create `.semgrep.yml` with command injection, SSRF, and secrets-in-code rules. If semgrep is not installed, write the config file and log that live scan was skipped.
   - **detect-secrets:** Add `.pre-commit-config.yaml` entry. If detect-secrets is not installed, write the config and log that baseline was skipped.
   - **llm-guard:** Add `security = ["llm-guard"]` under `[tool.poetry.extras]` in `pyproject.toml`. Add the configurable Dispatcher hook (off by default, checked via `importlib.util.find_spec`). Do NOT require llm-guard to be installed.
4. **B07-S13** — Author `docs/security/brimley-0.7-threat-model.md` covering all 7 threat categories from the plan: Command Injection, SSRF, HTTP Header Injection, Prompt Injection, Secret Exfiltration, Path Traversal, Timeout/Resource Exhaustion. For each: vector, likelihood, impact, mitigations implemented in v0.7.

### Regression gate

After all steps are committed, run:

```bash
poetry run python -m pytest tests/test_security_cli_injection.py tests/test_security_api_injection.py -q
poetry run python -m pytest
poetry run bandit -r src/brimley -ll
```

Record all results in the Validation Plan section of the plan.

---

## Handoff to Wave 4

When all four steps are complete, committed, and the security gate passes (full suite green + Bandit zero violations), invoke the `@brimley-0.7-wave-4` agent to proceed with Wave 4 (examples, documentation, version bump, final validation).

Do NOT begin Wave 4 work in this session — stop after reporting the final Wave 3 status summary.
