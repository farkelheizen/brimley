---
name: brimley-0.7-preamble
description: Shared autonomy rules and conventions for all Brimley 0.7 implementation waves. Not invoked directly — embed in each wave agent.
---

You are implementing Brimley 0.7 per the plan in `docs/copilot/plans/brimley-0.7-plan.md`.

## Autonomy Grant

I grant explicit approval for this run to execute the steps listed in my task prompt without pausing for additional approval between steps. Operate autonomously in implementation mode. Do not ask for decision-gate confirmation after each step. You are authorized to create multiple commits and push them. Do NOT stop and ask "should I proceed?" between steps.

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
