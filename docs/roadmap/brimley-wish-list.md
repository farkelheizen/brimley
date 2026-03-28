# Brimley Wish List

> Status: Deferred ideas — not scheduled for any specific version.
> Last updated: 2026-03-28

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

## WL-002 — Telemetry Configuration Block (`brimley.yaml`)

**Origin:** Surfaced during [Brimley 0.9 Application Server & Managed Tasks](brimley-0.9-application-server-and-managed-tasks.md) design.

**Problem:**

Managed Tasks (v0.9) generate per-iteration metrics (success/failure counts, duration, last run time) that need to be recorded somewhere. The original v0.9 design spec proposed a `telemetry:` configuration block in `brimley.yaml` with `metrics_db`, `enabled`, and `retention_days` fields. However, this block is a cross-cutting concern that extends well beyond tasks — it's the natural foundation for function execution telemetry, token usage tracking, cache hit rates, and the DuckDB introspection milestone (v0.12).

Including it in v0.9 risks either shipping a half-baked system that v0.12 must rework, or expanding v0.9's scope significantly. For v0.9, task metrics will be emitted as structured log lines that v0.12 can later ingest.

**Proposed: `telemetry:` block in `brimley.yaml`**

```yaml
brimley:
  telemetry:
    metrics_db: "internal_analytics"  # refers to a db_connections entry
    enabled: true
    retention_days: 30
```

- **`metrics_db`**: Names a connection from the `db_connections` section. If omitted, defaults to an internal project-scoped DuckDB instance.
- **Unified Metrics**: Reusable for function execution times, token usage, cache hit rates, and task iteration telemetry.
- **`retention_days`**: Auto-prune old records to prevent unbounded storage growth.

**Open questions:**

1. Should telemetry be opt-in or opt-out? An `enabled: true` default could surprise users who don't expect background writes.
2. Should the DuckDB default instance be created lazily (on first metric write) or eagerly at startup?
3. What is the schema for the metrics tables? Should it be opinionated (fixed columns) or extensible (JSON blob column for arbitrary metadata)?
4. Should the `/sql SELECT ... FROM brimley_tasks` introspection query surface (Section 5 of the tasks spec) be bundled with the telemetry config, or remain a v0.12 feature?

**Target milestone:** v0.12 (DuckDB Introspection & REPL Analytics) — natural home for a unified telemetry backend.

---

## WL-003 — Single-File Distribution (`brimley build --bundle`)

**Origin:** Surfaced during [Brimley 0.9 Application Server & Managed Tasks](brimley-0.9-application-server-and-managed-tasks.md) design, when evaluating forward compatibility of the application server boundary with `brimley build`.

**Problem:**

Today `brimley build` generates a `brimley_assets.py` shim module that embeds SQL and template function metadata as decorated stubs (`return None`). This enables runtime discovery via `scan_module()` but does not produce a self-contained executable artifact. Distributing a Brimley project still requires shipping the full source tree (`.sql`, `.md`, `.yaml`, `.py` files) plus a Brimley installation.

The vision: a developer should be able to run `brimley build --bundle` and produce a single distributable file (or minimal archive) that another machine can execute with just `brimley run app.brm` (or similar), without the original source tree.

**Proposed approach:**

1. **SQL & Template functions** — already handled. The body text (SQL query, Jinja2 template) is embedded as string literals in generated shims. No behavioral gap.

2. **Python functions** — the core challenge. The current AST-only scan extracts metadata (decorator kwargs, signatures, annotations, docstrings) without importing the module. A build step that produces executable output must perform a **real import** of each Python function module, because:
   - Dynamic type resolution (runtime annotations, `TYPE_CHECKING` guards) can differ from AST string annotations.
   - Module-level side effects, conditional imports, and validation logic only execute on import.
   - Pydantic model validation and custom validators never run under AST-only scanning.
   
   The build step should:
   - Import each Python module in a controlled environment.
   - Validate that AST-extracted metadata matches import-time metadata (decorator kwargs, signatures).
   - Flag discrepancies as build diagnostics (warnings or errors).
   - Bundle the source (or compiled `.pyc` bytecode) into the artifact.

3. **Providers, lifecycle hooks, tasks** — same treatment as Python functions: real import at build time, bundled into the artifact.

4. **Configuration** — `brimley.yaml` and any `db_connections` definitions would be embedded in the bundle, possibly with environment-variable placeholders for secrets.

5. **Artifact format** — options include:
   - A zipapp (PEP 441) — single `.pyz` file, native Python support.
   - A custom archive with a Brimley-specific loader.
   - A generated single `.py` file with embedded assets (limits size but maximizes portability).

**Compatibility with application server boundary (v0.9):**

Removing embedding support does **not** conflict with single-file distribution. The built artifact is still a Brimley-owned process — `brimley run` would own the event loop, manage the `TaskScheduler`, and control shutdown. "Build" is about *how the runtime is assembled*, not *who owns the runtime*.

**Open questions:**

1. Should the bundle include Brimley itself (fully self-contained) or assume Brimley is installed on the target machine?
2. How should secrets and environment-specific config be handled? Baked-in defaults with env-var overrides? A separate `.env` file alongside the bundle?
3. Should the AST-vs-import validation be a standalone `brimley validate --deep` command (useful independent of bundling)?
4. What is the dependency story? If user code imports `httpx`, `pydantic`, etc., do those get bundled (PyInstaller-style) or listed as prerequisites?
5. Should `brimley build` gain a `--verify` flag that does the AST-vs-import comparison without producing a bundle, as an intermediate deliverable before full bundling?

**Target milestone:** Unscheduled — depends on the maturity of `brimley build` and the plugin architecture (v0.14). Likely post-v1.0.

---

## WL-004 — Per-Task `shutdown_timeout`

**Origin:** Surfaced during [Brimley 0.9 Application Server & Managed Tasks](brimley-0.9-application-server-and-managed-tasks.md) design (shutdown grace period decision).

**Problem:**

The v0.9 spec defines a global 30-second grace period for task cancellation during shutdown. This is pragmatic for the initial release, but real-world deployments may have tasks with very different shutdown profiles — a lightweight polling task might need 2 seconds, while a batch reconciler talking to an external API might need 60 seconds. A single global value forces the operator to set it high enough for the slowest task, which delays shutdown for all tasks.

**Proposed: `shutdown_timeout` key in the `task` dict**

```python
@function(
    name="slow_reconciler",
    task={"interval": "5m", "shutdown_timeout": "60s"},
)
async def reconcile(ctx: BrimleyContext):
    ...
```

- If `shutdown_timeout` is set, the `TaskScheduler` uses it as the per-task grace period instead of the global default.
- The global default remains the fallback for tasks that don't specify a value.
- The total shutdown wait is bounded by `max(all per-task timeouts)` rather than `sum(...)`, since tasks are cancelled concurrently.

**Open questions:**

1. Should the global default also be configurable (e.g., in `brimley.yaml` under a `tasks:` block), or is 30 seconds always the right default?
2. Should the per-task timeout be a hard upper bound (task is always cancelled at that point), or should the `TaskScheduler` attempt a soft signal first (e.g., set a cancellation flag the task can check)?

**Target milestone:** Unscheduled — backwards-compatible addition to the `task` dict. Can ship in any post-v0.9 release.

---

## WL-005 — `/task restart <name>` REPL Command

**Origin:** Surfaced during [Brimley 0.9 Application Server & Managed Tasks](brimley-0.9-application-server-and-managed-tasks.md) design (hot-reload behavior for scheduling metadata).

**Problem:**

Task scheduling metadata (`interval`, `immediate`, `retries`, `retry_interval`) is immutable at runtime in v0.9. If a developer changes a task's interval in source code, the hot-reload engine detects the change but only emits a warning — the developer must restart Brimley to apply it. This is safe but slightly inconvenient during development.

A `/task restart <name>` REPL command would stop a single task's scheduling loop, re-read the updated metadata from the reloaded `BrimleyFunction`, and start a new scheduling loop — without restarting the entire server. This is REPL-only (not available in `mcp-serve` mode).

**Proposed behavior:**

1. `/task restart github_reconciler` — stops the running task loop, re-reads metadata, starts a new loop.
2. If the task is currently mid-iteration, waits for the current iteration to complete (or cancels after a short timeout), then restarts with the new metadata.
3. Only available in REPL mode. In `mcp-serve` mode, the command is not exposed.

**Open questions:**

1. Should `/task restart` also reset the retry counter and backoff state, or preserve them?
2. Should there be a `/task stop <name>` and `/task start <name>` pair for finer control?
3. How does this interact with the `/tasks` listing — should `/tasks` show a `restarting` state during the transition?

**Target milestone:** Unscheduled — depends on the `/tasks` introspection command (v0.9) proving out the REPL task management UX.

---

## WL-006 — `cron` Task Property

**Origin:** Surfaced during [Brimley 0.9 Application Server & Managed Tasks](brimley-0.9-application-server-and-managed-tasks.md) design.

**Problem:**

The v0.9 task system uses a fixed `interval` for scheduling (e.g., "every 5 minutes"). This covers the most common use case — periodic polling and reconciliation — but cannot express calendar-aware schedules like "every day at 2:00 AM" or "every Monday at midnight." Cron-style scheduling is a natural extension for tasks that need time-of-day or day-of-week alignment.

**Proposed: `cron` key in the `task` dict**

```python
@function(
    name="nightly_cleanup",
    task={"cron": "0 2 * * *"},  # Every day at 2:00 AM
)
async def cleanup(ctx: BrimleyContext):
    ...
```

- `cron` and `interval` are **mutually exclusive**. The Scanner should reject a function that declares both (skip + warn), consistent with the existing quarantine rules.
- Uses standard 5-field cron syntax (`minute hour day month weekday`).
- `immediate` still applies — if `True`, the task fires once at startup regardless of the cron schedule.
- `retries` and `retry_interval` apply the same way as for interval-based tasks.

**Open questions:**

1. Should Brimley use a third-party cron parser (e.g., `croniter`) or implement a minimal subset?
2. How does overlap prevention interact with cron? A cron task that takes longer than the gap between scheduled runs has the same problem as an interval-based task.
3. Should there be an `at` shorthand for simple daily schedules (e.g., `task={"at": "02:00"}`) to avoid requiring full cron syntax for the common case?

**Target milestone:** Unscheduled — natural follow-up once the interval-based scheduler is proven in production.

---

## WL-007 — `jitter` Task Property

**Origin:** Surfaced during [Brimley 0.9 Application Server & Managed Tasks](brimley-0.9-application-server-and-managed-tasks.md) design.

**Problem:**

When a Brimley instance has many tasks with the same `interval` (e.g., ten tasks all set to `"5m"`), they will all fire at exactly the same time on every iteration — creating a periodic spike in resource usage (CPU, network, database connections). This "thundering herd" pattern is especially problematic when tasks make external API calls with rate limits.

Adding a random jitter to each task's scheduling delay spreads the load more evenly and reduces contention.

**Proposed: `jitter` key in the `task` dict**

```python
@function(
    name="github_reconciler",
    task={"interval": "5m", "jitter": "30s"},
)
async def reconcile(ctx: BrimleyContext):
    ...
```

- `jitter` specifies a maximum random offset added to each scheduling delay. The actual delay for each iteration is `interval + random(0, jitter)`.
- Uses the same human-time parser as `interval`.
- If omitted, no jitter is applied (current v0.9 behavior).
- Jitter applies to the scheduled delay, not to retry intervals.

**Open questions:**

1. Should jitter be applied to the first `immediate=True` firing, or only to subsequent iterations?
2. Should the jitter range be symmetric (±jitter, centered on the interval) or one-sided (0 to +jitter)?
3. Should there be a global jitter setting in `brimley.yaml` that applies to all tasks, overridable per-task?

**Target milestone:** Unscheduled — low implementation effort, but only valuable for instances with many concurrent tasks.

---

## WL-008 — MCP Server Authentication (`mcp.auth` Config Block)

**Origin:** Surfaced during [Brimley 0.9 Application Server & Managed Tasks](brimley-0.9-application-server-and-managed-tasks.md) design, when considering remote deployment scenarios under the application server model.

**Problem:**

Brimley's MCP server (`mcp-serve` and REPL embedded MCP) currently has no authentication. This is acceptable for local development (stdio is unauthenticated by convention, and SSE on localhost is fine for dev), but it is a hard prerequisite for any remote deployment. Without auth, any network client can invoke Brimley tools — including tools that modify databases, call external APIs, or access secrets.

FastMCP 3.x already ships a comprehensive auth subsystem: OAuth 2.1 server, JWT/static token verification, pre-built third-party providers (GitHub, Google, Azure, Auth0, AWS, etc.), OAuth proxy for enterprise IdPs, per-tool scope gating, and global auth middleware. Brimley should reuse this rather than inventing its own.

**Proposed: `mcp.auth` config block in `brimley.yaml`**

```yaml
mcp:
  host: 127.0.0.1
  port: 8000
  auth:
    provider: github              # github | google | azure | jwt | static | none
    client_id: ${GITHUB_CLIENT_ID}
    client_secret: ${GITHUB_CLIENT_SECRET}
    required_scopes: ["read"]     # global scope requirement for all tools
```

**Design approach:**

1. **Provider mapping:** Brimley maps the `provider` string to the corresponding FastMCP auth provider class (`GitHubProvider`, `JWTVerifier`, `StaticTokenVerifier`, etc.). Credentials flow through the existing `secrets:` resolution chain or environment variable interpolation.

2. **Server wiring:** Pass `auth=` when constructing the `FastMCP(...)` server instance. This affects two code paths: the `mcp-serve` command and the REPL embedded MCP server.

3. **Per-tool authorization (optional):** Map Brimley function metadata (e.g., a `scopes` field on the MCP config) to FastMCP's component-level `auth` checks (`require_scopes()`, `restrict_tag()`). This allows fine-grained access control per tool.

4. **stdio bypass:** FastMCP's auth middleware auto-skips for stdio transport by convention. No special handling needed.

**FastMCP auth capabilities (as of 3.1.x):**

| Mechanism | FastMCP Class | Use Case |
|---|---|---|
| OAuth 2.1 server | `OAuthProvider` / `InMemoryOAuthProvider` | Full authorization server |
| JWT verification | `JWTVerifier` | Validate tokens against a JWKS endpoint |
| Static bearer token | `StaticTokenVerifier` | Simple shared-secret auth |
| Third-party provider | `GitHubProvider`, `GoogleProvider`, etc. | Delegate to GitHub, Google, Azure, Auth0, AWS, etc. |
| OAuth proxy | `OAuthProxy` | Proxy to upstream enterprise IdP |
| OIDC proxy | `OIDCProxy` | OpenID Connect providers |
| Per-tool scopes | `require_scopes()` / `restrict_tag()` | Component-level authorization |
| Global middleware | `AuthMiddleware` | Blanket auth across all tools |
| Debug verifier | `DebugTokenVerifier` | Accept any token (testing only) |

**Open questions:**

1. Should `auth.provider: none` be the default (opt-in auth), or should Brimley warn when serving over SSE with no auth configured?
2. Should per-tool scopes be declared in the function's `mcp:` metadata (e.g., `mcp: { type: tool, scopes: ["write"] }`) or in a centralized `brimley.yaml` mapping?
3. How should the `InMemoryOAuthProvider` (test/dev) be exposed? A `provider: debug` shorthand?
4. Should Brimley support multiple auth providers simultaneously (e.g., JWT for API clients + OAuth for browser-based clients), or is single-provider sufficient?

**Target milestone:** Unscheduled — prerequisite for any remote/production deployment. Could ship as a standalone minor release once the application server model (v0.9) is stable.

---

## How to use this document

When a new deferred idea surfaces during a version increment:

1. Add a new `WL-NNN` entry with **Origin**, **Problem**, **Proposed solution(s)**, and **Open questions**.
2. Link back to the version doc or plan that triggered the idea.
3. Do not block the current version on it — that is the point of this list.
4. When an item is scheduled for implementation, move it to a proper plan doc under `docs/roadmap/` and remove or mark it here as `Promoted → <plan doc>`.
