# Brimley Quickstart

Go from zero to a working SQL agent tool in 5 minutes.

## 1. Install Brimley

*(Assuming you are installing from a local build or a future PyPI release)*

```bash
pip install brimley

```

## 2. Project Setup

Create a new directory for your project and set up the standard folder structure:

```bash
mkdir my_agent
cd my_agent
mkdir tools data

```

## 3. Seed a Test Database

Brimley needs a database to talk to. Let's create a simple SQLite database with some dummy data.
Run this Python snippet once:

```python
# setup_db.py
import sqlite3

# Connect to (or create) the database file
conn = sqlite3.connect("data/local.db")
cursor = conn.cursor()

# Create a table and add a row
cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, role TEXT)")
cursor.execute("INSERT OR IGNORE INTO users (id, name, role) VALUES (1, 'Alice', 'Admin')")
conn.commit()

print("Database created at data/local.db")

```

## 4. Create Your First Tool

Define a tool that reads from this database. Create a file named `tools/get_user.json`.

**File:** `tools/get_user.json`

```json
{
  "tool_name": "get_user_by_id",
  "tool_type": "LOCAL_SQL",
  "description": "Retrieves user details by their ID.",
  "action": "GET",
  "implementation": {
    "sql_template": [
      "SELECT * FROM users",
      "WHERE id = :target_id"
    ]
  },
  "return_shape": {
    "type": "RECORD"
  },
  "arguments": {
    "inline": [
      {
        "name": "target_id",
        "type": "int",
        "required": true
      }
    ]
  }
}

```

## 5. Run It!

Now use the Brimley Engine to load your tool and execute it.

**File:** `run_agent.py`

```python
from brimley.core import BrimleyEngine

# 1. Initialize the Engine
# Point it to your tools folder and your database
engine = BrimleyEngine(
    tools_dir="tools", 
    db_path="data/local.db"
)

# 2. Simulate an Agent calling the tool
print("🤖 Agent is calling 'get_user_by_id'...")

result = engine.execute_tool(
    tool_name="get_user_by_id", 
    tool_args={"target_id": 1}
)

# 3. View the Result
print("✅ Result:", result)

```

Run the script:

```bash
python run_agent.py

```

**Expected Output:**

```text
🤖 Agent is calling 'get_user_by_id'...
✅ Result: {'id': 1, 'name': 'Alice', 'role': 'Admin'}

```
