# Plan: Brimley MCP Server Implementation

## Phase 1: Structure & Setup

**Goal:** Establish a home for the server code within the repo.

1.  **Create Directory Structure:**
    *   Initialize `src/brimley_mcp/`.
    *   Add `src/brimley_mcp/__init__.py`.
    *   Add `src/brimley_mcp/main.py` (CLI entrypoint).
    *   Add `src/brimley_mcp/adapter.py` (Brimley -> FastMCP logic).

2.  **Dependencies:**
    *   Add `fastmcp` to `pyproject.toml` (likely as an optional dependency group `[mcp]` or a separate package dependency if we split).
    *   Add `typer` or `click` for robust CLI parsing.

## Phase 2: The Adapter (Core Logic)

**Goal:** Refactor the "magic" from `examples/mcp_server/server.py` into a reusable, robust class.

1.  **Port `server.py` logic to `adapter.py`:**
    *   Create class `BrimleyMCPAdapter(brimley_engine, fastmcp_server)`.
    *   Implement method `register_tools()`.
    *   Refine the **Dynamic Function Generation** to be safer and more compatible with introspection. The current `exec()` method in the example is hacky; we should investigate `makefun` or `pydantic` dynamic models more deeply to avoid `exec` if possible, though `exec` is often necessary for signature masking in Python.

## Phase 3: The CLI

**Goal:** Create the executable command.

1.  **Implement `src/brimley_mcp/main.py`:**
    *   Use `typer` to define the version and `start` command.
    *   Validation: Ensure `db_path` and `tools_dir` exist before starting.
    *   Import path handling: Ensure `extensions_file` is loaded correctly (sys.path hacks might be needed to allow loading arbitrary python files).

2.  **Configuration:**
    *   Allow loading from `.env` or defaults? (Likely out of scope for V1, stick to args).

## Phase 4: Packaging

**Goal:** Make it installable as `pip install brimley[server]` or `pip install brimley-mcp`.

1.  **Update `pyproject.toml`:**
    *   Define the CLI entrypoint:
        ```toml
        [project.scripts]
        brimley-mcp = "brimley_mcp.main:app"
        ```

## Phase 5: Testing & Verification

**Goal:** Ensure the server implementation is robust and correct.

1.  **Unit Tests:**
    *   Create `tests/test_mcp_adapter.py`.
    *   Test that Brimley tools are correctly converted to FastMCP tools (check names, descriptions, arguments).
    *   Test dynamic signature generation logic.
    *   Mock `BrimleyEngine` and verify that the adapter calls `execute_tool` correctly.

2.  **Refactor Example (Integration Verification):**
    *   Delete the code in `examples/mcp_server/server.py` and replace it with a call to the new library or run it via the new CLI to verify parity.

## Phase 6: Configuration & DX (Developer Experience)

**Goal:** Reduce friction for local development and deployment.

1.  **Environment Variables:**
    *   Integrate `python-dotenv` to load configuration from a `.env` file if present.
    *   Support standard variables: `BRIMLEY_DB_PATH`, `BRIMLEY_TOOLS_DIR`, `BRIMLEY_EXTENSIONS_FILE`.
    *   **Precedence:** CLI Arguments > Environment Variables > Defaults (if any).

2.  **Defaults:**
    *   If no config provided, check for convenient defaults (e.g., look for `tools/` and `data.db` in current working directory).

## Phase 7: Logging & Observability

**Goal:** Allow debugging without breaking the MCP protocol.

1.  **Stdio Isolation:**
    *   The MCP protocol uses `stdout` for communication. Any stray `print()` statement will crash the connection.
    *   Implement a logging configuration that forces all logs to `stderr` or a file.

2.  **Debug Mode:**
    *   Add a `--debug` flag to the CLI that increases verbosity on `stderr`.

## Phase 8: Documentation

**Goal:** Teach users how to stand up the server.

1.  **New Guide:** Create `docs/MCP_SERVER_GUIDE.md`.
    *   Instructions for generic usage.
    *   Specific instructions for Claude Desktop integration.
2.  **Update README:** Add a section on "Running as a Server".

## Checklist

- [x] Create `src/brimley_mcp`
- [x] Add Dependencies (`pyproject.toml`)
- [x] Implement `Adapter` logic
- [x] Implement `CLI`
- [x] Update `pyproject.toml`
- [x] Test with `examples/mcp_server` data
- [x] Documentation & Guides
