# Tool Schema Reference

This document serves as the definitive guide for defining **Brimley Tools**.

Tools are defined as **JSON** or **YAML** files located in your project's `tools/` directory. Each file represents a discrete capability that your agent or application can execute.

---

## 1. The Root Object

Every tool definition file must contain a single root object with the following properties:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `tool_name` | `string` | **Yes** | A unique identifier (snake_case). Used by the code to invoke the tool. |
| `tool_type` | `string` | **Yes** | The execution engine to use. Supported: `LOCAL_SQL`, `PROMPT_BUILDER`. |
| `description` | `string` | **Yes** | Crucial for AI Agents. Explains *what* the tool does and *when* to use it. |
| `action` | `string` | No | Semantic intent: `GET` (Read), `UPDATE` (Write/Delete), `EXECUTE`. |
| `implementation` | `object` | **Yes** | The specific logic for the tool (depends on `tool_type`). |
| `return_shape` | `object` | **Yes** | Defines the structure of the data returned by the tool. |
| `arguments` | `object` | **Yes** | Defines the input parameters required to run the tool. |

---

## 2. Tool Types & Implementation

### A. `LOCAL_SQL`

Executes a parameterized SQL query against the configured database (e.g., SQLite).

**Implementation Properties:**

* **`sql_template`** (`List[string]`): The SQL query. Can be split into multiple lines for readability. Use `:param_name` for arguments.

**Example:**

```json
"implementation": {
  "sql_template": [
    "SELECT * FROM customers",
    "WHERE id = :customer_id"
  ]
}

```

### B. `PROMPT_BUILDER` (Coming Soon)

*Note: This feature is currently in development and not yet available.*

Loads external text templates, fills in variables (Jinja2), and returns a constructed prompt string or chat object.

**Implementation Properties:**

* **`template_files`** (`List[string]`): Paths to template files (relative to your templates directory).
* **`engine`** (`string`): Templating engine. Default: `"jinja2"`.
* **`output_format`** (`string`):
* `"STRING"`: Returns a single concatenated string.
* `"CHAT_MESSAGES"`: Returns a list of message objects (requires `role_mapping`).



---

## 3. Arguments Schema

The `arguments` block defines the inputs your tool accepts. Brimley uses these to validate input before execution.

You can mix **Inline Arguments** (manual definitions) with **Entity References** (pre-defined schemas).

### Structure

```json
"arguments": {
  "entity_ref": "OptionalEntityName", 
  "inline": [
    {
      "name": "arg_name",
      "type": "string",       // int, float, string, bool
      "required": true,
      "default": "some_value" // Optional
    }
  ]
}

```

### Common Primitive Types

* `int`: Integer numbers (e.g., `105`)
* `float`: Decimal numbers (e.g., `99.99`)
* `string`: Text (e.g., `"active"`)
* `bool`: Boolean (e.g., `true` or `false`)

---

## 4. Return Shapes

The `return_shape` block tells the consumer (or AI) what format the data will arrive in.

| Type | Description | Best For |
| --- | --- | --- |
| **`TABLE`** | A list of dictionaries/rows. | `SELECT * ...` (returning multiple rows) |
| **`RECORD`** | A single dictionary/row. | `SELECT ... LIMIT 1` or `UPDATE ... RETURNING *` |
| **`VALUE`** | A single primitive value. | `SELECT count(*) ...` or `PROMPT_BUILDER` (String output) |
| **`LIST`** | A list of primitives. | `SELECT distinct category ...` |
| **`VOID`** | No return data (just success/fail). | Simple `UPDATE`, `DELETE`, `INSERT` |

**Example:**

```json
"return_shape": {
  "type": "TABLE",
  "entity_ref": "Customer" // Optional semantic hint
}

```

---

## 5. Examples (Copy & Paste)

### Example 1: Basic SELECT (Read)

```json
{
  "tool_name": "get_customer_orders",
  "tool_type": "LOCAL_SQL",
  "description": "Retrieves all past orders for a specific customer.",
  "action": "GET",
  "implementation": {
    "sql_template": [
      "SELECT * FROM orders",
      "WHERE customer_id = :customer_id",
      "LIMIT :limit"
    ]
  },
  "return_shape": {
    "type": "TABLE",
    "entity_ref": "Order"
  },
  "arguments": {
    "inline": [
      { "name": "customer_id", "type": "int", "required": true },
      { "name": "limit", "type": "int", "default": 5 }
    ]
  }
}

```

### Example 2: UPDATE with Return (Write)

*Note: Uses SQLite `RETURNING` clause to get the new data immediately.*

```json
{
  "tool_name": "update_inventory",
  "tool_type": "LOCAL_SQL",
  "description": "Updates the stock count for a product and returns the new record.",
  "action": "UPDATE",
  "implementation": {
    "sql_template": [
      "UPDATE products",
      "SET stock = :new_stock",
      "WHERE sku = :sku",
      "RETURNING *"
    ]
  },
  "return_shape": {
    "type": "RECORD",
    "entity_ref": "Product"
  },
  "arguments": {
    "inline": [
      { "name": "sku", "type": "string", "required": true },
      { "name": "new_stock", "type": "int", "required": true }
    ]
  }
}

```

### Example 3: Prompt Builder (Template)

```json
{
  "tool_name": "build_summary_prompt",
  "tool_type": "PROMPT_BUILDER",
  "description": "Generates a prompt to summarize text, injecting user guidelines.",
  "action": "GET",
  "implementation": {
    "template_files": ["tasks/summarize.j2"],
    "engine": "jinja2",
    "output_format": "STRING"
  },
  "return_shape": {
    "type": "VALUE",
    "primitive_type": "string"
  },
  "arguments": {
    "inline": [
      { "name": "text_to_summarize", "type": "string", "required": true },
      { "name": "tone", "type": "string", "default": "professional" }
    ]
  }
}

```