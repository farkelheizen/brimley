# Brimley Extensions Guide

This guide is for **Python Developers** who need to extend Brimley beyond standard SQL operations.

Brimley allows you to inject custom Python logic into the engine using an **Extensions File**. This enables you to:

1. Create **Custom SQLite Functions (UDFs)** (e.g., regex, fuzzy matching, math).
2. Create **Custom Tool Runners** (e.g., send Slack messages, call REST APIs, run scripts).

---

## 1. Setup

To use extensions, you must create a Python file (conventionally named `extensions.py`) in your project root and point Brimley to it in your configuration.

**Directory Structure:**

```text
my-project/
├── brimley_config.yaml
├── extensions.py         <-- Your custom code lives here
├── tools/
│   └── ...

```

**Configuration (`brimley_config.yaml`):**

```yaml
database_path: "data/local.db"
extensions_file: "extensions.py"  # Path relative to the config file

```

---

## 2. Custom SQLite Functions (UDFs)

Standard SQLite is powerful, but sometimes you need Python's ecosystem (e.g., `fuzzywuzzy`, `math`, `datetime`). You can register Python functions so they can be called directly inside your SQL templates.

### Step A: Write the Extension (`extensions.py`)

Use the `@brimley.register_sqlite_function` decorator.

```python
import brimley
import math

# Example 1: A simple math function missing from older SQLite versions
@brimley.register_sqlite_function(name="calculate_hypotenuse", num_args=2)
def py_hypot(a, b):
    return math.sqrt(a*a + b*b)

# Example 2: Fuzzy String Matching (requires 'pip install rapidfuzz')
from rapidfuzz import fuzz

@brimley.register_sqlite_function(name="fuzzy_match_score", num_args=2)
def py_fuzzy_score(val1, val2):
    """Returns a score from 0 to 100 indicating similarity."""
    if not val1 or not val2:
        return 0
    return fuzz.ratio(str(val1), str(val2))

```

### Step B: Use it in a Tool (`tools/find_similar.json`)

You can now use `fuzzy_match_score` inside your SQL template as if it were a native command.

```json
{
  "tool_name": "find_similar_products",
  "tool_type": "LOCAL_SQL",
  "implementation": {
    "sql_template": [
      "SELECT product_name, fuzzy_match_score(product_name, :search_term) as score",
      "FROM products",
      "WHERE score > 80",
      "ORDER BY score DESC"
    ]
  },
  "return_shape": { "type": "TABLE" },
  "arguments": {
    "inline": [ { "name": "search_term", "type": "string" } ]
  }
}

```

---

## 3. Custom Tool Runners (Coming Soon)

*Note: This feature is planned but not yet implemented.*

If you need a tool that does something other than touch a database or build a prompt—like sending an API request or executing a shell command—you can register a **Custom Runner**.

### Step A: Write the Extension (`extensions.py`)

Use the `@brimley.register_runner` decorator. You must define a unique `tool_type` string.

**The Contract:**

* **Input:** `tool_def` (Dict), `args` (Dict of validated arguments).
* **Output:** Must return a JSON-serializable Dictionary (or `None`).

```python
import brimley
import requests

@brimley.register_runner("SLACK_WEBHOOK")
def run_slack_tool(tool_def, args):
    """
    Executes tools with tool_type="SLACK_WEBHOOK"
    """
    # 1. Get implementation details from the JSON definition
    webhook_url = tool_def['implementation'].get('webhook_url')
    
    if not webhook_url:
        return {"error": "Configuration missing webhook_url"}

    # 2. Construct the payload using runtime arguments
    payload = {
        "text": f"Alert: {args.get('message')}",
        "channel": args.get('channel', '#general')
    }

    # 3. Perform the action
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        return {"status": "success", "code": response.status_code}
    except Exception as e:
        return {"status": "error", "details": str(e)}

```

### Step B: Use it in a Tool (`tools/alert_team.json`)

Now you can define tools that use this new `SLACK_WEBHOOK` type.

```json
{
  "tool_name": "notify_dev_team",
  "tool_type": "SLACK_WEBHOOK", 
  "description": "Sends a message to the engineering slack channel.",
  "implementation": {
    "webhook_url": "https://hooks.slack.com/services/T000/B000/XXXX"
  },
  "return_shape": { "type": "VOID" },
  "arguments": {
    "inline": [
      { "name": "message", "type": "string", "required": true }
    ]
  }
}

```

---

## 4. Best Practices

1. **Keep it Fast:** Extensions run in the main thread. Do not put long `sleep()` calls or heavy computation in a synchronous runner, or you will block the agent.
2. **Error Handling:** Always wrap your logic in `try/except` blocks. If your Python code crashes, the entire Brimley engine (and the Agent) may crash. Return a dictionary with `{"error": "..."}` instead.
3. **Dependencies:** If your extension requires external libraries (like `requests` or `pandas`), document them in your project's `requirements.txt` so other developers know to install them.