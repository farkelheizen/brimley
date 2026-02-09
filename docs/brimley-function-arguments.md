# Brimley Function Arguments
> Version 0.2

This specification defines the syntax and validation rules for **Brimley Arguments**, used to define inputs for Tools (SQL, API, Python) and Prompts.

## 1. Global Structure

Arguments are defined as a Dictionary containing two primary keys. Both are optional, but at least one must be present if the tool requires input.

| **Key**      | **Type** | **Description**                                                                                                                               |
| ------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_ref` | `string` | A reference to a named Entity (e.g., `User`). Inherits all properties of that Entity as arguments.  The Entity must be dictionary-compatable. |
| `inline`     | `dict`   | Manual argument definitions. Supports **Shorthand**, **Complex**, or **JSON Schema** modes.                                                   |

---

## 2. The `inline` Argument Modes

The Brimley parser determines the complexity of the arguments based on the "fingerprint" of the `inline` dictionary.

### A. Shorthand Mode (Type-only)

- **Trigger:** Values are primitive type strings.
- **Use Case:** Quick scripts and simple parameters.
- 
```YAML
inline:
  customer_id: int
  is_active: bool
```

### B. Complex Mode (Brimley Metadata)

- **Trigger:** Values are dictionaries, but the top-level `inline` key does **not** contain `properties`.
- **Use Case:** Adding defaults, constraints, and descriptions.

```YAML
inline:
  limit:
    type: int
    default: 10
    maximum: 100
    description: "Number of records to return"
```
### C. Standard Mode (JSON Schema)

- **Trigger:** The `inline` dictionary contains the `properties` key.
- **Use Case:** Strict industry-standard compliance and copy-pasting existing schemas.

```YAML
inline:
  properties:
    customer_id: { type: integer }
  required: [customer_id]
```

---

## 3. Context Mapping (`from_context`)

Arguments can be automatically populated from the [BrimleyContext](brimley-context.md) instead of being provided by the caller or an LLM. This is useful for security-sensitive fields like user IDs or environmental configuration.

When an argument defines `from_context`, the framework resolves the value at execution time using dot-notation.

|**Scope**|**Description**|**Example Path**|
|---|---|---|
|`app`|Application or session state.|`app.user.id`|
|`config`|Static system configuration.|`config.api.timeout`|

**Example:**

```
args:
  inline:
    # Provided by user
    reason: string
    # Automatically injected from system state
    actor_id:
      type: string
      from_context: "app.user.id"
```


## 4. Supported Primitive Types

Brimley maps the following shorthand keywords to their respective data types and JSON Schema formats.


| **Shorthand**   | **JSON Schema Type**         | **Python Type** | **SQL Equivalent**    |
| --------------- | ---------------------------- | --------------- | --------------------- |
| **`int`**       | `integer`                    | `int`           | `BIGINT`              |
| **`float`**     | `number`                     | `float`         | `DOUBLE` / `FLOAT8`   |
| **`decimal`**   | `number`                     | `Decimal`       | `NUMERIC` / `DECIMAL` |
| **`bool`**      | `boolean`                    | `bool`          | `BOOLEAN`             |
| **`string`**    | `string`                     | `str`           | `TEXT` / `VARCHAR`    |
| **`date`**      | `string` (format: date)      | `date`          | `DATE`                |
| **`datetime`**  | `string` (format: date-time) | `datetime`      | `TIMESTAMP`           |
| **`primitive`** | `[string, number, boolean]`  | `Any`           | `N/A`                 |

---

## 5. Collection Support

Any primitive or Entity reference can be turned into a list/table by appending `[]`.
- **`int[]`**: A list of integers.
- **`User[]`**: A collection of objects matching the `User` Entity.
The exception would be for the `entity_ref` argument.  When defined, this must be a string that points to a named dictionary-compatible JSON schema entity.

---

## 6. Implementation Example (Full Spec)

**Example**: arguments for get_orders tool that fetches customer orders with optional filtering:
```YAML
arguments:
  entity_ref: Customer # Inherits Customer fields
  inline:
    status:
      type: string
      default: "shipped"
      enum: ["pending", "shipped", "cancelled"]
    min_total: float
    start_date: date
    user_id:
      type: string
      from_context: "app.user.id"
```

## 7. Resource Path Parameters

When a resource has path parameters, it will require an `arguments` property.  All of the same rules apply.

**Example:** `/docs/{category}/{sub_category}/{doc_index}`
```YAML
arguments:
  entity_ref: ~
  inline:
    category: string
    sub_category: string
    doc_index: int
```

#### Handling "Wildcards" (The Catch-all)

If you want to allow a user to pass an arbitrary number of sub-paths (e.g., `/docs/engineering/hardware/sensors/v1`), you should support a **`splat`** or **`remainder`** type:

**Example:** `/docs/{category}/{remainder*}`

```YAML
arguments:
  entity_ref: ~
  inline:
    category: string
    remainder: string # This would capture "hardware/sensors/v1"
```
