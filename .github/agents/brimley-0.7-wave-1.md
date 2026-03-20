---
name: brimley-0.7-wave-1
description: Brimley 0.7 Wave 1 — foundational domain models, SecretsResolver, YAML scanner, and BaseRunner ABC (B07-S1 through B07-S4).
---

You are implementing Brimley 0.7 per the plan in `docs/copilot/plans/brimley-0.7-plan.md`.

## Autonomy Grant

I grant explicit approval for this run to execute steps B07-S1 through B07-S4 without pausing for additional approval between steps. Operate autonomously in implementation mode. Do not ask for decision-gate confirmation after each step. You are authorized to create multiple commits and push them. Do NOT stop and ask "should I proceed?" between steps.

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
- `docs/decisions/0002-accelerate-api-cli-to-v0.7.md`
- `docs/decisions/0003-secrets-block-ordered-resolution.md`

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

## Wave 1 Scope: B07-S1 → B07-S2 → B07-S3 → B07-S4

Execute steps B07-S1, B07-S2, B07-S3, and B07-S4 from the plan. These are the foundational steps and must be executed in order, as S3 (scanner) depends on models from S1 and secrets validation from S2.

### Step order

1. **B07-S1** — Add `ApiFunction`, `CliFunction`, `ApiRequestConfig`, `ResultMapping` models to `src/brimley/core/models.py`; add `secrets` field to `BrimleyFunction` base.
2. **B07-S2** — Implement `SecretsResolver` in `src/brimley/infrastructure/secrets.py` with `env` source resolution, `provider` startup error, and two-layer log redaction.
3. **B07-S3** — Extend `Scanner` for `.yaml` file discovery; add `src/brimley/discovery/yaml_parser.py` for `api_function`/`cli_function` parsing.
4. **B07-S4** — Define `BaseRunner` ABC in `src/brimley/execution/base_runner.py` (existing runners do NOT need to be retrofitted in this step).

### Regression gate

After all four steps are committed, run:

```bash
poetry run python -m pytest tests/test_models.py tests/test_secrets.py tests/test_yaml_parser.py tests/test_discovery.py tests/test_execution.py -q
poetry run python -m pytest
```

Record results in the Validation Plan section of the plan.

---

## Handoff to Wave 2

When all four steps are complete, committed, and the full test suite passes, invoke the `@brimley-0.7-wave-2` agent to proceed with Wave 2 (ApiRunner, CliRunner, Dispatcher, MCP, httpx).

Do NOT begin Wave 2 work in this session — stop after reporting the final Wave 1 status summary.
