# Brimley 0.6: Logging Architecture

## Overview

Brimley 0.6 introduces a robust logging framework designed for modern asynchronous execution and Model Context Protocol (MCP) compatibility. The architecture centers on **Loguru** to provide structured, contextual logging that unifies Brimley's internal runners with third-party frameworks like FastMCP.

## Core Requirements

### 1. Request Correlation IDs

To untangle concurrent logs, Brimley 0.6 implements a "Get or Create" correlation ID pattern.

- **Lifecycle:** A unique `correlation_id` (8-character UUID) is generated at the start of a top-level `Dispatcher.run()` call.
    - The `Dispatcher` checks for an existing ID in the current `contextvars` before generating a new one.
        
    - Nested calls (e.g., a Python function calling a SQL function via `context`) inherit the parent's ID.
        
- **Async/Thread Safety:** IDs are stored via `ContextVar` to ensure they persist across `asyncio` context switches and `ThreadPoolExecutor` threads.
    
- **Context Access:** `BrimleyContext` exposes a read-only `correlation_id` property for use in external system headers.

#### 1.1 OpenTelemetry Alignment

To align with distributed tracing standards, Brimley tracks an external trace identifier alongside the local `correlation_id`:

- **`external_trace_id`:** When present, sourced from FastMCP `mcp_ctx.request_id`.
- **Fallback:** If no upstream request id exists, Brimley falls back to `correlation_id` for local-only tracing.
- **Logging Contract:** Both ids are included in log `extra` so JSONL sinks can be joined with upstream telemetry.
- **Context Access:** `BrimleyContext` exposes read-only `external_trace_id` and `correlation_id`.
    

### 2. FastMCP & Third-Party Unification

Brimley acts as the logging authority for side-loaded frameworks:

- **Log Hijacking:** Brimley implements an `InterceptHandler` to redirect standard Python `logging` calls (used by FastMCP and its dependencies) into the `Loguru` stream.
    
- **Unified Stream:** This ensures that internal FastMCP logs are decorated with the same `correlation_id` as the Brimley functions they are executing.
    

### 3. Dual-Sink Strategy

Brimley 0.6 supports simultaneous output to multiple destinations to balance protocol safety with debugging depth.

- **Primary Sink (stderr):**
    
    - **Always Enabled:** Mandatory for MCP compatibility.
        
    - **Purpose:** Allows MCP hosts (like Claude Desktop) to capture debug info without corrupting the `stdout` JSON-RPC stream.
        
- **Optional File Sink:**
    
    - **Configuration:** Defined in `brimley.yaml` under `brimley.logging.file`.
        
    - **JSONL Support:** File sinks should support a `format: jsonl` option. When enabled, logs are written as newline-delimited JSON objects, including all `extra` fields (like `correlation_id`).
        
    - **Management:** Supports `rotation` (e.g., `10 MB` or `daily`) and `retention` (e.g., `1 week`).
        
    - **Depth:** Can be configured for higher verbosity (`DEBUG`) than the console/stderr sink.
        

### 4. Logging Format & Caller Attribution

The standard output pattern ensures clear traceability.

- **The Dispatcher Problem:** By default, wrapping execution in a dispatcher causes logs to attribute the location to `brimley.execution.dispatcher:run:92`.
    
- **Caller Overrides:** Brimley runners must use Loguru's `opt(depth=...)` or dynamic record patching to ensure that logs reflect the actual file, function, and line number of the code being executed (the "User-Land" code).
    
- **Standard Pattern:** `[YYYY-MM-DD HH:mm:ss] | INFO | [ID: 8a2f1b3c] | {caller} - {message}`
    

### 5. Pluggable Logging Providers

For enterprise environments or specific runtime constraints:

- **Custom Handlers:** Users should be able to provide a custom logging provider class that adheres to the Brimley Logging Interface.
    
- **Framework Bypass:** A configuration flag (`brimley.logging.managed: false`) allows users to disable Brimley's automatic Loguru setup if they wish to handle global logging manually, though they lose automatic correlation ID propagation unless they implement the Brimley contract.
### 6. Logging Configuration (brimley.yaml)

Logging is configured under the `brimley.logging` section in `brimley.yaml`:

```yaml
brimley:
  logging:
    # Global default level for all loggers (set on stderr sink)
    level: INFO
    
    # Module-level overrides (Log4J style)
    # Maps logger name patterns to specific levels
    modules:
      brimley.execution: DEBUG      # Verbose execution tracing
      brimley.mcp: INFO             # MCP adapter logs
      fastmcp: WARNING              # Third-party framework logs
      sqlalchemy: WARNING           # SQL dialect warnings
    
    # File sink configuration
    file:
      path: logs/brimley.log        # Log file path (relative to project root)
      level: DEBUG                  # File sink can be more verbose than stderr
      format: jsonl                 # 'text' (default) or 'jsonl' for structured logs
      rotation: 10 MB               # Rotate on file size: "10 MB", "daily", etc.
            retention: 7 days             # Keep logs: "7 days", "4 weeks", etc.
    managed: true                   # Set to false to disable Brimley's Loguru setup
```

**Precedence Order (highest to lowest):**

1. CLI flags (`--log-level`, `--log-module`)
2. REPL runtime commands (`/log-level`, `/log-module`)
3. `brimley.yaml` (`brimley.logging.*`)
4. Model defaults (`INFO` for stderr, `DEBUG` for file)

**CLI Override Examples:**

```bash
# Set global level for stderr
brimley repl --log-level DEBUG

# Override a specific module at runtime
brimley repl --log-module "brimley.execution:TRACE" --log-module "fastmcp:WARNING"

# Multiple module overrides
brimley run my_function.py --log-module "app:DEBUG" --log-module "sqlalchemy:ERROR"
```

**REPL Runtime Commands:**

Once in the REPL, dynamic level changes (answering the roadmap feedback concern):

```
/log-level INFO                          # Change global level (immediate effect)
/log-level brimley.execution DEBUG       # Override specific module (immediate)
/log-modules                             # Show current module overrides
/log-reset                               # Reset to config defaults
```
    

## Implementation Details

### ContextVar Storage

A global `ContextVar` handles the storage of the ID, ensuring that `Loguru` can access it via the `extra` field in its record factory.

### Loguru Configuration Logic

```python
from loguru import logger
import sys

def init_logging(config, cli_overrides=None):
    logger.remove()  # Remove default sink
    
    # Resolve effective levels
    stderr_level = config.logging.level  # e.g., "INFO"
    file_level = config.logging.file.level  # e.g., "DEBUG"
    
    # Apply CLI overrides
    if cli_overrides:
        if cli_overrides.global_level:
            stderr_level = cli_overrides.global_level
        if cli_overrides.module_levels:
            config.logging.modules.update(cli_overrides.module_levels)
    
    # Configure stderr with global level and correlation_id injection
    logger.add(
        sys.stderr,
        format="[{time:YYYY-MM-DD HH:mm:ss}] | {level: <8} | [ID: {extra[correlation_id]:.8}] | [TRACE: {extra[external_trace_id]}] | {name}:{function}:{line} - {message}",
        level=stderr_level,
        filter=lambda record: _log_filter(record, stderr_level, config.logging.modules)
    )
    
    # Configure file sink if enabled
    if config.logging.file.path:
        is_json = config.logging.file.format == "jsonl"
        logger.add(
            config.logging.file.path,
            rotation=config.logging.file.rotation,
            retention=config.logging.file.retention,
            serialize=is_json,
            level=file_level,
            filter=lambda record: _log_filter(record, file_level, config.logging.modules)
        )

def _log_filter(record, global_level, module_levels):
    """Inject context ids and enforce global/module thresholds."""
    record["extra"]["correlation_id"] = get_correlation_id()
    record["extra"]["external_trace_id"] = get_external_trace_id()

    logger_name = record["name"] or ""
    threshold = global_level

    # Longest-prefix match gives deterministic module-level behavior.
    for module_name, module_level in sorted(module_levels.items(), key=lambda kv: len(kv[0]), reverse=True):
        if logger_name == module_name or logger_name.startswith(module_name + "."):
            threshold = module_level
            break

    levels = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
    current = record["level"].name
    return levels.index(current) >= levels.index(threshold)

def get_external_trace_id():
    """Return upstream trace id (FastMCP request id) or fallback to correlation_id."""
    return get_mcp_request_id() or get_correlation_id()

def get_mcp_request_id():
    """Read request id from MCP context when available."""
    # Implement using the active MCP request context in runtime adapter.
    return None
```

**Module-Level Filtering Mechanism:**

Module-level thresholds are implemented in a sink `filter` function by matching `record["name"]` against configured module prefixes and selecting the most specific match. This provides Log4J-style per-module levels while preserving a global default.

### 7. Per-Correlation ID Logging Level Overrides

For debugging single in-flight requests, Brimley supports temporary level overrides keyed by `correlation_id`.

**Behavior:**
- Overrides apply only to the targeted correlation id.
- Other concurrent requests keep normal module/global thresholds.
- Overrides are removed at request completion (or explicit reset).

```python
from contextvars import ContextVar

_cid_level_overrides: ContextVar[dict[str, str]] = ContextVar("_cid_level_overrides", default={})

def set_correlation_level(correlation_id: str, level: str) -> None:
    overrides = _cid_level_overrides.get().copy()
    overrides[correlation_id] = level.upper()
    _cid_level_overrides.set(overrides)

def clear_correlation_level(correlation_id: str) -> None:
    overrides = _cid_level_overrides.get().copy()
    overrides.pop(correlation_id, None)
    _cid_level_overrides.set(overrides)

def _module_threshold(logger_name, global_level, module_levels):
    threshold = global_level
    for module_name, module_level in sorted(module_levels.items(), key=lambda kv: len(kv[0]), reverse=True):
        if logger_name == module_name or logger_name.startswith(module_name + "."):
            threshold = module_level
            break
    return threshold

def _effective_threshold(record, global_level, module_levels):
    threshold = _module_threshold(record["name"], global_level, module_levels)
    cid = record["extra"].get("correlation_id")
    if cid and cid in _cid_level_overrides.get():
        threshold = _cid_level_overrides.get()[cid]
    return threshold
```

**Ingress and runtime controls:**
- FastMCP ingress can set request-level debug via header/metadata at request start.
- REPL command: `/log-level-for-id <correlation_id> <LEVEL>` sets a temporary override.
- REPL command: `/log-level-for-id <correlation_id> --clear` removes it.



### Dispatcher Integration

The `Dispatcher.run` method wraps the execution in a `logger.contextualize` block. To fix caller attribution, runners use: `logger.opt(depth=1).info("Executing user code")`

**Dynamic Level Changes:**

When users change log levels via REPL commands, the change is **immediate**:

```python
class REPLEnvironment:
    def cmd_log_level(self, args):
        """
        /log-level DEBUG                         # Set global level
        /log-level brimley.execution TRACE       # Set module-specific level
        """
        tokens = args.split()
        if len(tokens) == 1:
            # Update global level on stderr sink
            logger.remove()  # Remove stderr sink
            logger.add(sys.stderr, level=tokens[0].upper(), ...)
            logger.info(f"Global level set to {tokens[0].upper()}")
        elif len(tokens) == 2:
            module, level = tokens[0], tokens[1].upper()
            set_module_level(module, level)
            logger.info(f"Module '{module}' set to {level}")
        else:
            logger.warning("Usage: /log-level <LEVEL> or /log-level <MODULE> <LEVEL>")
```

This approach avoids process restart and applies to **all following logs**, answering the roadmap concern about seamless dynamic log levels in the REPL.