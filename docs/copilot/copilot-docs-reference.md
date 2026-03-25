# Copilot Docs Reference Map (Brimley)
> Docs baseline: 0.8.x

Use this file as the fast lookup index before implementation.

## Documentation Versioning Convention

- Treat specs as baseline docs (for example, `0.7.x`), not exact release trackers.
- Keep exact versions in `pyproject.toml`, `CHANGELOG.md`, and release tags.
- Update a spec doc only when that doc's behavior/content changed.
- Use body markers like `Introduced in 0.6+` only when they add semantic clarity.

## Quick Routing Rules

1. **Need architecture context first?**
   - Open: `docs/brimley-high-level-design.md`
2. **Need runtime/command behavior?**
   - Open: `docs/brimley-cli-and-repl-harness.md`
3. **Need data contract details (args/returns/entities)?**
   - Open: `docs/brimley-function-arguments.md`, `docs/brimley-function-return-shape.md`, `docs/brimley-entities.md`
4. **Need discovery/parser/loader behavior?**
   - Open: `docs/brimley-discovery-and-loader-specification.md`
5. **Need MCP behavior and tool exposure rules?**
   - Open: `docs/brimley-model-context-protocol-integration.md`
6. **Need config or context fields?**
   - Open: `docs/brimley-configuration.md`, `docs/brimley-context.md`
7. **Need to understand *why* a roadmap or architectural decision was made?**
   - Open: `docs/decisions/README.md` for the index, then the relevant numbered ADR.

---

## Topic → Primary Doc → Supporting Docs

| Topic | Primary Doc | Supporting Docs |
|---|---|---|
| Architecture overview, lifecycle, data flow | `docs/brimley-high-level-design.md` | `docs/brimley-project-structure.md`, `docs/brimley-application-structure.md` |
| CLI commands (`invoke`, `repl`, `mcp-serve`, `build`) | `docs/brimley-cli-and-repl-harness.md` | `docs/brimley-repl-admin-commands.md`, `docs/brimley-configuration.md` |
| REPL admin commands and behavior | `docs/brimley-repl-admin-commands.md` | `docs/brimley-cli-and-repl-harness.md` |
| Config file schema (`brimley.yaml`) and env interpolation | `docs/brimley-configuration.md` | `docs/brimley-context.md`, `docs/brimley-sql-execution.md` |
| Context object fields and lifecycle | `docs/brimley-context.md` | `docs/brimley-configuration.md`, `docs/brimley-high-level-design.md` |
| Discovery/parsing/scanning/registration | `docs/brimley-discovery-and-loader-specification.md` | `docs/brimley-diagnostics-and-error-reporting.md`, `docs/brimley-project-structure.md` |
| Diagnostics and Wall-of-Shame behavior | `docs/brimley-diagnostics-and-error-reporting.md` | `docs/brimley-discovery-and-loader-specification.md` |
| Function metadata and supported types | `docs/brimley-functions.md` | `docs/brimley-python-functions.md`, `docs/brimley-sql-functions.md`, `docs/brimley-template-functions.md`, `docs/brimley-api-functions.md`, `docs/brimley-cli-functions.md` |
| Argument inference, typing, `from_context` | `docs/brimley-function-arguments.md` | `docs/brimley-python-functions.md`, `docs/brimley-cli-and-repl-harness.md` |
| Return shape syntax and runtime mapping | `docs/brimley-function-return-shape.md` | `docs/brimley-entities.md`, `docs/brimley-sql-functions.md` |
| Python decorators, injection, reload metadata | `docs/brimley-python-functions.md` | `docs/brimley-discovery-and-loader-specification.md`, `docs/brimley-model-context-protocol-integration.md` |
| SQL frontmatter, params, connection usage | `docs/brimley-sql-functions.md` | `docs/brimley-sql-execution.md`, `docs/brimley-function-arguments.md` |
| SQLAlchemy execution and relative SQLite path semantics | `docs/brimley-sql-execution.md` | `docs/brimley-configuration.md` |
| Template function semantics and template context scope | `docs/brimley-template-functions.md` | `docs/brimley-function-arguments.md` |
| API function schema, result parsing, SSRF/header injection mitigations | `docs/brimley-api-functions.md` | `docs/brimley-secrets.md`, `docs/brimley-model-context-protocol-integration.md`, `docs/roadmap/brimley-0.7-api-functions.md` |
| CLI function schema, subprocess exec, metachar validation, exit-code handling | `docs/brimley-cli-functions.md` | `docs/brimley-secrets.md`, `docs/brimley-model-context-protocol-integration.md`, `docs/roadmap/brimley-0.7-cli-functions.md` |
| Secrets resolution, ordered sources, log redaction, `BrimleySecretResolutionError` | `docs/brimley-secrets.md` | `docs/brimley-api-functions.md`, `docs/brimley-cli-functions.md`, `docs/decisions/0003-secrets-block-ordered-resolution.md` |
| Dependency injection, `BrimleyContainer`, `@provider`, `Depends()`, `@on_startup`, `@on_shutdown`, singleton/request scope, provider teardown | `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` | `docs/brimley-python-functions.md`, `docs/brimley-context.md`, `docs/brimley-discovery-and-loader-specification.md`, `docs/brimley-secrets.md` |
| Security: threat model, injection mitigations, SSRF, prompt injection screening | `docs/security/brimley-0.7-threat-model.md` | `docs/brimley-api-functions.md`, `docs/brimley-cli-functions.md`, `docs/brimley-configuration.md` |
| MCP tool exposure, schema filtering, embedded server | `docs/brimley-model-context-protocol-integration.md` | `docs/brimley-cli-and-repl-harness.md`, `docs/brimley-python-functions.md`, `docs/brimley-api-functions.md`, `docs/brimley-cli-functions.md` |
| Naming and identifier constraints | `docs/brimley-naming-conventions.md` | `docs/brimley-functions.md` |
| Logging, observability, correlation IDs, dual-sink, log levels, log format | `docs/roadmap/brimley-0.6-logging-architecture.md` | `docs/brimley-configuration.md`, `docs/brimley-repl-admin-commands.md`, `docs/brimley-cli-and-repl-harness.md` |
| Deferred feature ideas, future enhancements | `docs/roadmap/brimley-wish-list.md` | `docs/roadmap/index.md` |
| Architecture & roadmap decision history (ADRs) | `docs/decisions/README.md` | Individual ADR files in `docs/decisions/` |
| Repository/layout/dependency reference | `docs/brimley-project-structure.md` | `docs/brimley-application-structure.md` |
| App-level file layout for Brimley projects | `docs/brimley-application-structure.md` | `docs/brimley-project-structure.md` |

---

## Keyword Index (use when searching)

- **auto_reload, watcher, debounce, reload policy** → `brimley-application-structure.md`, `brimley-context.md`, `brimley-cli-and-repl-harness.md`
- **invoke pipeline, execute_function_by_name, input parsing** → `brimley-cli-and-repl-harness.md`
- **decorators `@function`, `@entity`, AST discovery** → `brimley-python-functions.md`, `brimley-discovery-and-loader-specification.md`, `brimley-entities.md`
- **MCP, FastMCP, tool schema filtering, embedded SSE** → `brimley-model-context-protocol-integration.md`
- **`from_context`, `AppState`, `Config`, argument precedence** → `brimley-function-arguments.md`, `brimley-cli-and-repl-harness.md`
- **`return_shape`, `Result Mapper`, entity mapping** → `brimley-function-return-shape.md`, `brimley-entities.md`
- **diagnostics, error codes, wall of shame** → `brimley-diagnostics-and-error-reporting.md`
- **SQL params, SQLAlchemy engine, `rows_affected`** → `brimley-sql-functions.md`, `brimley-sql-execution.md`
- **logging levels, Loguru, correlation ID, dual-sink, log hijacking, JSONL logs, --log-level, --log-module** → `docs/roadmap/brimley-0.6-logging-architecture.md`, `brimley-configuration.md`, `brimley-repl-admin-commands.md`
- **ADR, architecture decision, roadmap rationale, why was X deferred, release order** → `docs/decisions/README.md`
- **wish list, deferred features, future ideas, WL-** → `docs/roadmap/brimley-wish-list.md`
- **api_function, HTTP integration, httpx, url templating, SSRF, header injection** → `brimley-api-functions.md`, `docs/roadmap/brimley-0.7-api-functions.md`
- **cli_function, subprocess, command_arguments, shell injection, metachar, exit code** → `brimley-cli-functions.md`, `docs/roadmap/brimley-0.7-cli-functions.md`
- **secrets, secret resolution, env source, provider source, BrimleySecretResolutionError, log redaction** → `brimley-secrets.md`, `docs/decisions/0003-secrets-block-ordered-resolution.md`
- **security, threat model, prompt injection, llm-guard, bandit, detect-secrets, SSRF** → `docs/security/brimley-0.7-threat-model.md`, `brimley-api-functions.md`, `brimley-cli-functions.md`, `brimley-configuration.md`
- **ResultParser, result_parser, text parser, json parser, regex parser, results block** → `brimley-api-functions.md`, `brimley-cli-functions.md`
- **`@provider`, `Depends`, `BrimleyContainer`, `on_startup`, `on_shutdown`, DI, dependency injection, singleton, request scope, provider teardown, override** → `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md`, `brimley-python-functions.md`, `brimley-context.md`, `brimley-discovery-and-loader-specification.md`

---

## Copilot Usage Protocol

When implementing or fixing code:

1. Open **one primary doc** from the Topic table.
2. Open **1-2 supporting docs** only if needed.
3. Extract explicit constraints before coding (required fields, precedence, CLI behavior, error text).
4. If docs conflict, prefer the more specific functional spec over broad design text:
   - command behavior: `brimley-cli-and-repl-harness.md`
   - parser/discovery behavior: `brimley-discovery-and-loader-specification.md`
   - data contracts: `brimley-function-arguments.md` and `brimley-function-return-shape.md`
5. Record which docs were used in plan notes when a behavior decision is non-obvious.
