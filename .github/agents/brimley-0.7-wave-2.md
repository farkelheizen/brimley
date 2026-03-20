---
name: brimley-0.7-wave-2
description: Brimley 0.7 Wave 2 — ApiRunner, CliRunner, Dispatcher routing, MCP registration, and httpx dependency (B07-S5 through B07-S9).
---

You are implementing Brimley 0.7 per the plan in `docs/copilot/plans/brimley-0.7-plan.md`.

## Autonomy Grant

I grant explicit approval for this run to execute steps B07-S5 through B07-S9 without pausing for additional approval between steps. Operate autonomously in implementation mode. Do not ask for decision-gate confirmation after each step. You are authorized to create multiple commits and push them. Do NOT stop and ask "should I proceed?" between steps.

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

## Wave 2 Scope: B07-S9 → B07-S5 → B07-S6 → B07-S7 → B07-S8

Execute steps B07-S5 through B07-S9 from the plan. **Note the reordering:** S9 (httpx dependency) must be done first so that ApiRunner can import httpx. Log this ordering deviation in the S9 Step Notes.

### Step order

1. **B07-S9** — Add `httpx>=0.27,<1.0` to `pyproject.toml` core dependencies; run `poetry lock && poetry install` to validate. *(Done first despite plan ordering — log deviation in S9 notes.)*
2. **B07-S5** — Implement `ApiRunner` in `src/brimley/execution/api_runner.py`; add `ResultParser` ABC and `TextResultParser`/`JsonResultParser`/`RegexResultParser` in `src/brimley/execution/result_parser.py`. Include custom dot-path parser (SD-2). Use `jinja2.sandbox.SandboxedEnvironment` for all template rendering (OQ-9).
3. **B07-S6** — Implement `CliRunner` in `src/brimley/execution/cli_runner.py`. `shell=False` enforced via `asyncio.create_subprocess_exec`. Two-mode env behavior per OQ-8. Per-exit-code result dispatch with `empty: true` support.
4. **B07-S7** — Extend `Dispatcher` in `src/brimley/execution/dispatcher.py` with `api_function`/`cli_function` routing; add `SecretsResolver` integration; add v0.9 mock intercept stub comment.
5. **B07-S8** — Extend `BrimleyProvider` in `src/brimley/mcp/fastmcp_provider.py` to register `api_function`/`cli_function` tools; verify `secrets` fields are excluded from MCP schemas.

### Regression gate

After all steps are committed, run:

```bash
poetry run python -m pytest tests/test_execution.py tests/test_execution_python.py tests/test_execution_sql.py tests/test_execution_jinja.py tests/test_execution_api.py tests/test_execution_cli.py tests/test_mcp_provider.py tests/test_mcp_adapter.py -q
poetry run python -m pytest
```

Record results in the Validation Plan section of the plan.

---

## Handoff to Wave 3

When all five steps are complete, committed, and the full test suite passes, invoke the `@brimley-0.7-wave-3` agent to proceed with Wave 3 (security hardening: injection tests, Bandit/Semgrep, detect-secrets, threat model).

Do NOT begin Wave 3 work in this session — stop after reporting the final Wave 2 status summary.
