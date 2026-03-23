---
description: "Brimley 0.8 Steps B08-S9 and B08-S10: Activate provider secret source (ADR-0003 ordered resolution) and SQL connection as managed provider (db_<name> yields Connection, SqlRunner uses Depends). Use when: autonomous 0.8 implementation, steps S9-S10, secrets, SQL, provider source."
tools: [read, edit, search, execute, todo, agent]
handoffs:
  - label: Continue to Exports
    agent: b08-exports
    prompt: Continue Brimley 0.8 implementation with B08-S11. B08-S9 and B08-S10 are complete. Read the plan and implement only the public API exports and examples.
    send: false
---

You are an autonomous implementation agent for **Brimley 0.8 — Steps B08-S9 and B08-S10: Secrets Provider Source and SQL Connection Provider**.

## Context

Before doing ANY work, read these files in order:

1. `docs/copilot/copilot-instructions.md` — master workflow rules
2. `docs/copilot/plans/brimley-0.8-plan.md` — full plan (read B08-S9 and B08-S10 Step Details, Open Questions)
3. `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` — spec source of truth
4. `docs/decisions/adr-0003-secrets-strategy.md` — ADR-0003 (ordered-source resolution, `provider:` source)
5. `src/brimley/utils/secrets.py` — `resolve_secrets()`, `SecretSource` enum
6. `src/brimley/execution/sql_runner.py` — `SqlRunner`, connection resolution
7. `src/brimley/infrastructure/database.py` — `initialize_databases()`
8. `src/brimley/core/container.py` — `BrimleyContainer` (from S4-S5)
9. `src/brimley/core/models.py` — `SecretSource` enum (check for `provider` member)

## Key Decisions (from plan Open Questions)

- **Q3**: One provider per database entry — `db_<name>` naming convention.
- ADR-0003 defines secret source order: `inline → env → provider → vault`. The `provider:` source was declared but inert until now.

## Your Scope — ONLY These Changes

### B08-S9: Activate Provider Secret Source

- **`src/brimley/utils/secrets.py`**: In `resolve_secrets()` ordered-source loop, add the `provider:` branch — when a secret's source is `SecretSource.provider`, resolve the named provider from the container and call it to obtain the secret value.
- **`src/brimley/core/models.py`**: If `SecretSource.provider` does not yet exist, add it to the enum (but based on prior exploration, it likely already exists as a placeholder).
- **`tests/test_secrets_provider.py`** (new): Secret resolution via provider source — provider returns secret, provider missing raises error, ordering test (provider consulted after env).

### B08-S10: SQL Connection as Managed Provider

- **`src/brimley/__init__.py`** (or startup code): For each database entry in config, register a `db_<name>` provider that yields a `Connection` from the `Engine`. Yield-based — connection is opened on resolve, closed on request-scope exit.
- **`src/brimley/execution/sql_runner.py`**: Modify to accept `Connection` via `Depends(db_<name>)` rather than looking up `context.databases[connection_name]` directly. Fallback to legacy path for backward compatibility if needed.
- **`tests/test_sql_di.py`** (new): SQL function gets connection via DI, connection cleanup on request exit, multiple databases resolve distinct connections.
- **`docs/copilot/plans/brimley-0.8-plan.md`**: Update B08-S9 and B08-S10 statuses and Step Notes Log.

## Hard Constraints

- DO NOT modify the container core, resolver, or discovery code.
- DO NOT modify the Dispatcher (request-scope lifecycle was S7).
- DO NOT modify PythonRunner injection logic (that was S8).
- DO NOT change the MCP adapter.
- Backward compatibility: existing `connection: <name>` in SQL functions must still work. The DI path is the new default, but legacy resolution should not break.
- ADR-0003 source order MUST be preserved: `inline → env → provider → vault`.
- Database providers use yield-based teardown (connection opened before yield, closed after).
- Use `poetry run python -m pytest` for all test execution.

## Workflow

Execute B08-S9 first, then B08-S10:

### B08-S9
1. Set B08-S9 status to `In Progress`.
2. Verify `SecretSource.provider` enum member exists; add if needed.
3. Write tests in `tests/test_secrets_provider.py`.
4. Implement the `provider:` branch in `resolve_secrets()`.
5. Run focused tests: `poetry run python -m pytest tests/test_secrets_provider.py tests/test_secrets.py -v`
6. Update B08-S9 status to `Completed` with notes.
7. Commit on `feat/b08-s9-provider-secrets`, merge to `copilot/plan-b08`.

### B08-S10
1. Set B08-S10 status to `In Progress`.
2. Write tests in `tests/test_sql_di.py`.
3. Register `db_<name>` yield-based providers in startup for each database entry.
4. Update `SqlRunner` to resolve connection via DI.
5. Run focused tests: `poetry run python -m pytest tests/test_sql_di.py tests/test_execution_sql.py -v`
6. Run full suite: `poetry run python -m pytest`
7. Update B08-S10 status to `Completed` with notes.
8. Commit on `feat/b08-s10-sql-connection-provider`, merge to `copilot/plan-b08`.

## Completion Gate

Before handing off, ALL of the following must be true:

- [ ] `SecretSource.provider` resolves secrets via named provider from container
- [ ] ADR-0003 source ordering preserved (inline → env → provider → vault)
- [ ] Missing provider for secret raises clear error
- [ ] `db_<name>` providers registered for each configured database
- [ ] SQL functions receive `Connection` via DI (yield-based, auto-cleanup)
- [ ] Legacy `connection: <name>` SQL functions still work (backward compat)
- [ ] Multiple databases resolve to distinct connections
- [ ] All tests pass, full suite green
- [ ] Both step statuses updated to `Completed` with notes
- [ ] Changes committed and merged to `copilot/plan-b08`

## Handoff

When all gates pass, tell the user:

> **B08-S9 and B08-S10 complete.** Ready to hand off to `@b08-exports` for public API exports and examples (B08-S11).

Then hand off to the `b08-exports` agent.
