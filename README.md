# Brimley

**The Local-First SQL Toolbelt for AI Agents.**

Brimley is a lightweight Python framework that gives Large Language Models (LLMs) safe, structured access to local data. It allows you to define tools using simple JSON/SQL configurations, validates AI inputs using strict schemas, and executes them against SQLite.

## Why Brimley?

Most agent frameworks either let the AI write dangerous raw SQL or require you to write endless Python boilerplate. Brimley sits in the middle: **You write the SQL templates; the AI fills in the blanks.**

👉 [Read the Design Philosophy](./docs/DESIGN_PHILOSOPHY.md)

## Key Features

* **Zero-Code Tool Definitions:** Define tools in JSON or YAML.
* **Safe by Design:** Uses parameterized queries to prevent SQL injection.
* **Strict Validation:** Powered by **Pydantic** to catch AI hallucinations before execution.
* **Local First:** Built for SQLite, making it perfect for rapid prototyping and local analysis.
* **Extensible:** Add custom Python logic (UDFs) when SQL isn't enough.

## Documentation Map

| I want to... | Go here |
| --- | --- |
| **Define a new tool** | [📖 Tool Schema Reference](./docs/TOOL_SCHEMA_REFERENCE.md) |
| **Add custom Python logic** | [🔌 Extensions Guide](./docs/EXTENSIONS_GUIDE.md) |

## Quick Example

Define a tool in `tools/get_user.json`:

```json
{
  "tool_name": "get_user",
  "tool_type": "LOCAL_SQL",
  "implementation": { "sql_template": ["SELECT * FROM users WHERE id = :id"] },
  "return_shape": { "type": "RECORD" },
  "arguments": { "inline": [{ "name": "id", "type": "int" }] }
}

```

Run it in Python:

```python
from brimley.core import BrimleyEngine

engine = BrimleyEngine(tools_dir="tools", db_path="my_data.db")
result = engine.execute_tool("get_user", {"id": 1})

```

## Installation

```bash
pip install brimley

```

## License

MIT

## Author

**William W. Spratley**

* GitHub: [@farkelheizen](https://github.com/farkelheizen)