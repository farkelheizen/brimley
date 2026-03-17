# Brimley 0.13: Plugin Architecture (External Runners)

> **ADR Reference:** [ADR-0004](../decisions/0004-defer-plugin-architecture-to-v0.13.md) — deferred from the original v0.9 slot to v0.13.
>
> **Note on `BaseRunner`:** The `BaseRunner` interface ships in **v0.7** as Brimley's internal execution contract. `ApiRunner` and `CliRunner` implement it. v0.13 adds **dynamic external loading** of third-party runners — it does not redesign the interface.

## Overview

Brimley 0.13 opens the `BaseRunner` interface to the community. By adding dynamic plugin loading to the `brimley.yaml` `plugins:` block, developers can extend Brimley to support new execution environments (e.g., `lambda_function`, `grpc_function`, `deno_script`) without modifying the core.

## 1. The Runner Interface

Every function type in Brimley must implement the `BaseRunner` interface.

### Core Methods:

- **`can_handle(file_path, content) -> bool`**: Logic used by the `Scanner` to determine if a file should be registered to this runner.
    
- **`run(function_definition, args, context) -> Any`**: The async execution logic. This method receives the parsed function metadata and the runtime arguments.
    

## 2. Plugin Registration

Plugins are registered in the `brimley.yaml` configuration file. This allows Brimley to load the necessary Python modules at startup.

```
# brimley.yaml
plugins:
  - name: "brimley-lambda-plugin"
    module: "brimley_ext.lambda"
    config:
      region: "us-east-1"
```

## 3. Discovery & The "Handshake"

When Brimley initializes, it performs a "handshake" with each registered plugin:

1. **Load:** The `Dispatcher` loads the plugin module.
    
2. **Scan:** The `Scanner` iterates through the project files. For each file, it asks every registered runner: "Can you handle this?"
    
3. **Register:** If a runner returns `True`, the file is registered in the `Registry` with that runner's associated metadata.
    

## 4. Example: Creating a Custom "Deno" Runner

A developer wants to support `.ts` files executed via the Deno runtime.

```
# brimley_ext/deno.py
from brimley.runners import BaseRunner
import subprocess

class DenoRunner(BaseRunner):
    def can_handle(self, file_path, content):
        # Handle files ending in .ts that contain a @brimley decorator in comments
        return file_path.endswith(".ts") and "//@function" in content

    async def run(self, func_def, args, ctx):
        # Logic to execute 'deno run' and capture output
        process = await asyncio.create_subprocess_exec(
            "deno", "run", func_def.path, 
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate(input=json.dumps(args).encode())
        return json.loads(stdout)
```

## 5. Benefits of the Plugin Model

- **Unified Lifecycle:** Custom functions automatically get Correlation IDs, Loguru integration, and Mocking support because they are invoked through the central `Dispatcher`.
    
- **MCP Readiness:** Because the plugin provides metadata (name, description, args), the `Dispatcher` can automatically wrap a custom plugin function as an MCP Tool.
    
- **Community Ecosystem:** Developers can share runners for specific clouds (Azure, GCP), specific protocols (GraphQL, gRPC), or specific languages (Ruby, Go).
    

## 6. Context: `BaseRunner` Ships in v0.7

The `sql`, `api`, and `cli` runners already implement `BaseRunner` as first-party built-in runners starting in v0.7. They are **not** refactored in v0.13 — they already use the interface. v0.13 adds the dynamic loading mechanism so community-contributed runners can be registered via `brimley.yaml` without modifying core code.

The 200ms startup budget concern is addressed by lazy-loading: third-party runner modules are imported only when a file matches their `can_handle()` predicate, not at startup.

## References

- [ADR-0004: Defer Plugin Architecture to v0.13](../decisions/0004-defer-plugin-architecture-to-v0.13.md)
- [Brimley 0.7 API Functions](brimley-0.7-api-functions.md)
- [Brimley 0.7 CLI Functions](brimley-0.7-cli-functions.md)

