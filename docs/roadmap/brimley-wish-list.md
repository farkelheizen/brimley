# Brimley Wish List

> Status: Deferred ideas — not scheduled for any specific version.
> Last updated: 2026-03-16

This document captures feature ideas and design improvements that surfaced during development but were intentionally deferred to avoid delaying a version release. Each entry records where the idea came from, what problem it solves, and enough detail to revisit it later.

---

## WL-001 — Function-Level Logging Directives

**Origin:** Surfaced during [Brimley 0.6 Logging Architecture](brimley-0.6-logging-architecture.md) implementation.

**Problem:**

Brimley 0.6 introduced structured logging via Loguru with TRACE-level dispatcher entries (`Dispatching function 'X' (type=Y)` / `Function 'X' completed/failed`). This gives baseline observability for all function types, including SQL and template functions that have no Python body where a developer could add logging.

However, there is currently no way for a function author to:

- Control whether dispatcher-level TRACE entries are emitted for their specific function.
- Inject structured context (e.g. business-meaningful labels, extra fields) into the log record at call time.
- Set a minimum log level threshold specifically for one function (e.g. always log at INFO when this particular function runs, regardless of global level).
- Suppress dispatcher logging for very high-frequency utility functions that would produce noise.

**Proposed: YAML frontmatter directive (`logging:` in `.sql` / `.md` / `.yaml` function definitions)**

```yaml
# In a .sql function file
---
name: get_users
connection: default
logging:
  level: INFO           # Emit dispatch events at INFO instead of TRACE
  suppress: false       # Set true to disable all dispatcher log entries for this function
  extra:
    domain: "user-management"   # Extra fields injected into every log record for this function
---
SELECT * FROM users LIMIT :limit
```

**Proposed: `@function` decorator directive (Python)**

```python
@function(
    mcpType="tool",
    logging={"level": "DEBUG", "extra": {"domain": "billing"}},
)
def calculate_tax(amount: float, rate: float) -> float:
    ...
```

Or as a dedicated decorator argument:

```python
@function(mcpType="tool", log_level="DEBUG", log_extra={"domain": "billing"})
def calculate_tax(amount: float, rate: float) -> float:
    ...
```

**Proposed: Per-function log level in `brimley.yaml` (top-level config override)**

```yaml
logging:
  functions:
    calculate_tax: DEBUG
    get_users: INFO
    noisy_utility_fn: suppress
```

**Open questions:**

1. Should function-level log configuration live in the function definition file (frontmatter / decorator) or in `brimley.yaml`? The former is more portable; the latter separates ops concerns from code.
2. If both are supported, what is the precedence order? (Suggestion: CLI flag > `brimley.yaml` functions override > function definition directive > global module level > global default.)
3. Should `extra` fields be merged with correlation ID fields in the Loguru record, or appended under a namespaced key like `extra.fn`?
4. Should there be a `log_args: true` opt-in to include resolved argument values in the TRACE record (useful for debugging, risky for secrets)?

**Effort estimate:** Medium — requires changes to `BrimleyFunction` model, `LoggingSettings`, `Dispatcher`, and discovery parsers for all three function types.

---

## How to use this document

When a new deferred idea surfaces during a version increment:

1. Add a new `WL-NNN` entry with **Origin**, **Problem**, **Proposed solution(s)**, and **Open questions**.
2. Link back to the version doc or plan that triggered the idea.
3. Do not block the current version on it — that is the point of this list.
4. When an item is scheduled for implementation, move it to a proper plan doc under `docs/roadmap/` and remove or mark it here as `Promoted → <plan doc>`.
