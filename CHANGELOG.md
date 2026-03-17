# Changelog

All notable changes to Brimley are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.6.0] – 2026-03-16

### Added

- **Structured logging via Loguru** — Brimley now owns and configures the Loguru logging pipeline at startup. All internal logs use a consistent `[timestamp] | level | [ID: correlation_id] | module:fn:line - message` format.
- **Correlation IDs** — Every top-level `Dispatcher.run()` call gets a unique 8-character correlation ID stored in a `ContextVar`. Nested calls inherit the parent ID. Async and thread-pool contexts preserve the ID correctly.
- **External trace ID alignment** — When FastMCP provides a `request_id`, Brimley captures it as `external_trace_id` and falls back to `correlation_id` for local-only runs. Both fields are injected into every log record.
- **Dual-sink logging** — Stderr sink is always active (required for MCP transport compatibility). An optional file sink can be enabled via `logging.file` in `brimley.yaml`.
- **File sink features** — JSONL format (`format: jsonl`), rotation (`rotation: 10 MB`, `daily`, etc.), and retention (`retention: 7 days`, `4 weeks`, etc.). File sink level is independently configurable from the stderr sink.
- **Per-module level overrides** — Log4J-style prefix matching: `logging.modules` maps module name prefixes to log levels. Longest-prefix match wins.
- **CLI log overrides** — `--log-level` (global stderr level) and `--log-module MODULE:LEVEL` (per-module, repeatable) are now accepted by `brimley invoke`, `brimley repl`, and `brimley repl-daemon`.
- **REPL runtime log commands** — `/log-level`, `/log-level MODULE LEVEL`, `/log-modules`, `/log-reset` allow changing log verbosity without restarting the daemon.
- **Per-correlation runtime overrides** — In-flight log level overrides scoped to a specific correlation ID, used by the REPL `/log-level` commands.
- **FastMCP log interception** — An `InterceptHandler` redirects stdlib `logging` calls (used by FastMCP and SQLAlchemy) into the Loguru stream, decorating them with the same correlation ID as the surrounding Brimley execution.
- **`managed: false` escape hatch** — Setting `logging.managed: false` in `brimley.yaml` disables Brimley's Loguru setup entirely for environments that manage their own logging pipeline.
- **Top-level `logging:` key in `brimley.yaml`** — The `logging` configuration block is now accepted at the root level of `brimley.yaml` (previously it was only recognized when nested under `brimley:`).

### Fixed

- `load_config` was silently discarding the top-level `logging:` key because it was not in the allowed-keys allowlist. Log file sinks configured in `brimley.yaml` were never initialised.
- `BrimleyContext` was not forwarding the top-level `logging` dict to `FrameworkSettings`, so file sink settings (path, rotation, retention) were always `None` even when present in the config.

### Changed

- `logging.level` and `logging.file.level` now normalize all level strings to uppercase. Invalid levels raise a `ValueError` at config parse time.
- `load_config` allowed-keys list extended with `"logging"`.
- `examples/brimley.yaml` updated to use the top-level `logging:` key and demonstrate the full file-sink configuration.

---
