# Brimley (v0.4) 🎩

**The Fault-Tolerant Authoring Engine for AI Tools**

Brimley is an advanced execution environment designed to bridge the gap between local developer workflows and AI-driven tool execution (via the Model Context Protocol).

While most MCP frameworks focus on transport (how to send messages to the LLM), Brimley focuses on **Authoring and Execution**—giving developers a magical, instant-feedback loop for building complex agentic tools.

Think of the split this way: **Brimley is the Authoring Engine, FastMCP is the Transport Layer.**

## ✨ Why Brimley? (The Differentiators)

Writing tools for AI agents shouldn't require restarting your server every time you tweak a prompt or fix a bug. Brimley rethinks the tool-building lifecycle:

- 🔍 **Zero-Import AST Discovery:** Brimley discovers your tools by scanning Abstract Syntax Trees (AST). It reads metadata, docstrings, and type hints without importing the modules. Broken code in one file will never crash your server.
- 🔄 **Safe Instant Hot-Reloading:** Edit function logic, save, and Brimley promotes valid changes immediately. Broken changed objects are quarantined with explicit errors (no silent stale fallback).
- 🧪 **Developer Trust Surface:** Use `/errors` in the REPL for the live "wall of shame" and run `brimley validate --root .` for preflight diagnostics before shipping.
- 🌍 **Polyglot Tooling:** Why write Python just to execute a database query? Brimley treats `.py`, `.sql`, and `.md` files as first-class citizens.
- 💻 **The Hybrid REPL:** Test your tools manually in an interactive terminal while your LLM is connected to the exact same live-updating environment.

## 🚀 Quick Start

### 1. Installation

Brimley is lightweight by default, but to serve tools to an LLM, you'll want the FastMCP integration.

```
# Poetry project install with FastMCP transport support
poetry install -E fastmcp

# (Published package usage)
pip install "brimley[fastmcp]"
```

### 2. Project Initialization & Configuration

Brimley uses a `brimley.yaml` configuration file at your project root. This file does more than just name your project—it manages three critical layers of your environment out-of-the-box:

1. **Immutable Config:** Read-only settings (like URLs or emails) injected into your tools.
2. **Mutable State:** In-memory variables that persist across tool calls while the daemon runs.
3. **Database Pools:** Connection managers that automatically wire up to your SQL tools.

```
# brimley.yaml
name: my-ai-tools

# 1. Immutable configuration (accessible via context.config)
config:
    support_email: "help@example.com"

# 2. Mutable application state (accessible via context.state)
state:
    tools_called: 0

# 3. Database connection pools (automatically linked to .sql tools)
connections:
    default:
        type: sqlite
        url: "sqlite:///app.db"
```

### 3. Write a Tool

Create your `tools/` directory and drop in a Python file. Brimley discovers functions using the `@brimley.function` decorator, reading standard Python type hints and docstrings.

```
# tools/weather.py
import brimley

@brimley.function
def get_weather(location: str) -> str:
        """
        Fetches the current weather for a given location.

        Args:
                location: The city and state, e.g., 'San Francisco, CA'
        """
        return f"It is currently 72°F and sunny in {location}."
```

### 4. Test in the REPL

Before handing the tool to an AI, test it yourself using Brimley's interactive terminal. You'll specify your project root directly in the command. (When you run this command, Brimley will automatically start a background daemon if one isn't already running).

```
brimley repl --root .
```

```
Brimley Interactive REPL (v0.4)
Watching for changes...

brimley> get_weather location="New York, NY"
It is currently 72°F and sunny in New York, NY.
```

_Magic Trick:_ Leave the REPL running, change the temperature in `weather.py` to `60°F`, save the file, and hit the up arrow in your REPL. Brimley hot-reloads the function instantly.

If your edit introduces a broken signature or invalid metadata, Brimley surfaces a clear runtime/diagnostic error instead of silently serving old logic.

## 🌍 Polyglot Support

Brimley isn't just for Python. You can drop other file types directly into your root or tools directory.

### SQL Tools (`.sql`)

Define tools purely in SQL. Brimley parses the YAML front-matter block to define the tool schema for the LLM, and automatically routes the query to the `connection` defined in your `brimley.yaml`.

```
/*
---
name: get_users
type: sql_function
description: Retrieves users ordered by newest first with an optional row limit.
connection: default
return_shape: list[dict]
arguments:
    inline:
        limit:
            type: int
            default: 10
mcp:
    type: tool
---
*/

SELECT id, name, status, created_at
FROM users
ORDER BY created_at DESC
LIMIT :limit;
```

### Markdown Tools (`.md`)

Serve static content, standard operating procedures, or dynamically rendered templates directly to the LLM without writing any backend code.

```
---
name: hello
type: template_function
description: Renders a friendly welcome message using a provided name and support email.
return_shape: string
arguments:
    inline:
        name:
            type: string
            default: "World"
        support_email:
            type: string
            from_context: "config.support_email"
mcp:
    type: tool
---
# Hello {{ args.name }}!

Welcome to Brimley.

Contact us at: {{ args.support_email }}
```

## 🔌 Connecting to an LLM (FastMCP Integration)

Brimley 0.4 seamlessly delegates the networking layer to [FastMCP](https://github.com/jlowin/fastmcp).

When you are ready to deploy your tools natively in Python or connect them to an MCP client like Claude Desktop, you simply pass the `BrimleyProvider` to FastMCP. Brimley handles the hot-reloading execution, and FastMCP handles the standard input/output.

**Important:** logic-only changes can hot-reload; MCP schema-shape changes (argument/signature/default/requiredness) require provider reinitialization or process restart so clients receive updated schemas.

```
# server.py
from pathlib import Path

from fastmcp import FastMCP
from brimley.config.loader import load_config
from brimley.core.context import BrimleyContext
from brimley.discovery.scanner import Scanner
from brimley.mcp.fastmcp_provider import BrimleyProvider

# Initialize FastMCP
mcp = FastMCP("My Brimley Server")

# Build Brimley context from project root and attach provider
root = Path(".")
context = BrimleyContext(config_dict=load_config(root / "brimley.yaml"))
scan_result = Scanner(root).scan()
context.functions.register_all(scan_result.functions)

provider = BrimleyProvider(context.functions, context)
provider.register_tools(mcp_server=mcp)

if __name__ == "__main__":
        # Run the server
        mcp.run()
```

### 0.5 Migration Notes

- `BrimleyProvider` is the canonical MCP integration path.
- `BrimleyMCPAdapter` remains as a compatibility shim during migration.
- For host-managed refresh/reinit, prefer `ProviderMCPRefreshManager`; `ExternalMCPRefreshAdapter` remains compatibility naming.

### Hybrid Mode: Starting FastMCP via the REPL

Brimley operates as a background daemon when running the REPL. If there isn't a daemon running, the `brimley repl` command seamlessly creates one.

In this mode, the daemon owns MCP `stdio`; the REPL client talks only to the daemon over loopback API.

To instruct the daemon to also spin up FastMCP on `stdio` so your LLM can connect simultaneously, simply pass the `--mcp` flag:

```
brimley repl --root . --mcp
```

The LLM and the human developer are now targeting the exact same hot-reloaded code session, completely isolated from each other's I/O streams!

### Validate Before You Ship

Run a non-interactive validation pass to catch naming, parsing, and schema issues:

```
brimley validate --root .
```

## 🛠️ Advanced Usage

### Custom Embedded Applications

Need to embed Brimley inside an existing Discord bot, FastAPI server, or LangGraph workflow? Brimley's components are fully decoupled. You can manually instantiate the `Scanner`, `Registry`, and `PollingWatcher` to build entirely custom, hot-reloading execution environments.

See [Embedded Deployments & Port Management](docs/brimley-embedded-deployments-and-port-management.md) for hosting patterns, lifecycle ownership, and port strategy guidance.

### Migration Note (JSON Schema)

In v0.4, Brimley runtime authoring is FieldSpec-first (Python hints + Brimley metadata). Direct JSON Schema runtime authoring is no longer first-class; use the conversion utility path during migration.