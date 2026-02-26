# Brimley Embedded Deployments & Port Management
> Version 0.5

This guide covers practical deployment patterns when embedding Brimley into host applications, with special focus on MCP transport ownership, port allocation, and reload behavior.

## 1. Deployment Modes

### A. REPL Hybrid Mode (`brimley repl --mcp`)

Use this for local development when a human and an MCP client should target the same runtime session.

- REPL runs as a thin client (terminal I/O only).
- Brimley daemon process owns runtime state and embedded FastMCP hosting.
- MCP clients connect to configured host/port (default `127.0.0.1:8000`).

Notes:
- In 0.5, hybrid mode keeps MCP server runtime in daemon process context to avoid REPL/MCP stdio conflicts.
- Logic-only tool changes can refresh in place.
- MCP schema-shape changes require provider reinitialization/restart so clients can reconnect with updated schemas.
- Use `/detach` to disconnect thin client while keeping daemon running; use `repl --shutdown-daemon` (or daemon-side `/quit`) for shutdown.

### B. Dedicated MCP Server (`brimley mcp-serve`)

Use this for non-interactive tool serving.

- Brimley starts FastMCP hosting from CLI.
- Binding can be set by config (`mcp.host`, `mcp.port`) or CLI flags (`--host`, `--port`).
- Optional watch lifecycle can refresh/reinitialize tools as files change.

### C. External Host Embedding (FastAPI/LangGraph/Custom)

Use this when Brimley is a subsystem inside your app.

- Your app owns HTTP server lifecycle and process model.
- Brimley runtime controller/watcher manages discovery and registry refresh.
- `ProviderMCPRefreshManager` coordinates MCP tool refresh/reinit against your host-managed server instance (`ExternalMCPRefreshAdapter` remains compatibility naming).

## 2. Port Ownership Model

Treat MCP endpoints as a single-writer resource:

1. One process (or one host component) owns a given host:port binding.
2. One runtime controls tool registration for that MCP endpoint.
3. Clients reconnect when schema-shape changes require server/provider reinit.

### Default MCP Settings

```yaml
mcp:
  embedded: true
  transport: sse
  host: 127.0.0.1
  port: 8000
```

### CLI Override Precedence

For `mcp-serve`:

`--host/--port` > `brimley.yaml mcp.host/mcp.port` > model defaults.

## 3. Recommended Port Strategy

### Local Development

- Keep default `127.0.0.1:8000` for a single project.
- For parallel projects, assign distinct local ports (e.g., `8001`, `8002`).
- Keep REPL hybrid mode local-only unless you intentionally expose a bind address.

### Team/Shared Environments

- Reserve static port ranges per service/team.
- Front MCP endpoints with a reverse proxy when TLS/auth/routing policies are required.
- Expose health/readiness checks from the host process where possible.

### Production-like Embedding

- Prefer external host embedding with explicit lifecycle management.
- Ensure restart/reinit paths are handled for schema-shape changes.
- Avoid dynamic/random port assignment unless discovery/service-registry integration is already in place.

## 4. Watch Reload and Client Impact

When watch mode is enabled:

- **No schema-shape change:** wrappers/logic can refresh without client reconnect.
- **Schema-shape change:** reinitialize/restart MCP provider/server; clients must reconnect for updated tool schemas.
- **No reinit path available:** surface `client_action_required` and trigger operator restart flow.

## 5. Conflict Avoidance Checklist

Before starting an embedded deployment:

- Confirm target host:port is free.
- Confirm only one server instance is binding that endpoint.
- Confirm REPL mode is not competing with another MCP process on the same port.
- Confirm daemon lifecycle intent (detach vs shutdown) is clear for operators.
- Confirm your host has a defined reinit/restart path for schema-shape updates.
- Confirm client reconnection behavior is documented for operators/users.

## 6. Quick Examples

### Start dedicated MCP server on custom port

```bash
brimley mcp-serve --root . --host 127.0.0.1 --port 8010
```

### REPL hybrid with embedded MCP

```bash
brimley repl --root . --mcp
```

### External host-managed runtime controller

```python
from pathlib import Path

from brimley.runtime import BrimleyRuntimeController
from brimley.runtime.mcp_refresh_adapter import ProviderMCPRefreshManager

runtime = BrimleyRuntimeController(root_dir=Path("."))
runtime.load_initial()

refresh_manager = ProviderMCPRefreshManager(
    context=runtime.context,
    get_server=lambda: current_server,
    set_server=lambda server: set_current_server(server),
)

runtime.mcp_refresh = refresh_manager.refresh
runtime.start_auto_reload(background=True)
```

## 7. Rogue Process Triage (Check + Kill)

Use this runbook when REPL/MCP startup fails due to stale daemon state or occupied ports.

### 8.1 Check running Brimley/FastMCP processes

```bash
ps aux | grep -Ei 'brimley|fastmcp' | grep -v grep
```

Typical findings:
- `python ... -m brimley.cli.main repl-daemon ...` (daemonized REPL runtime)
- `python ... brimley/.venv/bin/pytest ...` (test processes that may still be active)
- `python ... brimley mcp-serve ...` (dedicated MCP server)

### 8.2 Check listening ports (especially 8000)

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep -Ei '8000|brimley|python'
```

If port `8000` is already bound, hybrid REPL or `mcp-serve` can fail to start.

### 8.3 Preferred shutdown (graceful)

From the project root:

```bash
poetry run brimley repl --root . --shutdown-daemon
```

This clears daemon/client lifecycle metadata and requests daemon shutdown when reachable.

### 8.4 Force-kill rogue processes

Kill by specific PID:

```bash
kill <PID>
```

If it does not terminate:

```bash
kill -9 <PID>
```

Or kill common stale classes directly:

```bash
pkill -f 'brimley.cli.main repl-daemon'
pkill -f '/.venv/bin/pytest'
```

### 8.5 Clean stale lifecycle metadata

If process is gone but daemon/client state remains, remove stale files:

```bash
rm -f .brimley/daemon.json .brimley/repl_client.json
```

### 8.6 Verify clean state

```bash
ps aux | grep -Ei 'brimley|fastmcp' | grep -v grep
lsof -nP -iTCP -sTCP:LISTEN | grep -Ei '8000|brimley|python'
```

Then restart desired mode (`repl --mcp` or `mcp-serve`).

## 8. Related Specs

- [MCP Integration](brimley-model-context-protocol-integration.md)
- [CLI & REPL Harness](brimley-cli-and-repl-harness.md)
- [Configuration](brimley-configuration.md)
- [High-Level Design](brimley-high-level-design.md)
