# Brimley 0.9: Plugin Architecture (Custom Function Types)

## Overview

Brimley 0.9 moves away from a hard-coded set of function types. By introducing a formal **Runner Plugin** interface, developers can extend Brimley to support new execution environments (e.g., `lambda_function`, `grpc_function`, or `deno_script`) by providing custom scanning and execution logic.

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
    

## 6. Internal Refactoring

To support this, the core `sql`, `api`, and `cli` runners in Brimley 0.9 will be refactored to use this exact same plugin interface, making the core of Brimley "dogfood" its own extensibility model.

References:
- [API Functions](./brimley-0.9-api-functions.md)
- [CLI Functions](./brimley-0.9-cli-functions.md)

## Unresolved Architectural Feedback

*   **Startup Time Impact (v1.0 Concern):** With a plugin registry initiating via YAML, achieving a 200ms startup is extremely ambitious for Python. Strict lazy-loading architectures will be necessary.
