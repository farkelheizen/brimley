# Brimley Function Arguments
> Version 0.3

This specification defines argument inference and validation rules for Brimley functions.

In 0.3, Python function signatures are the primary source for argument discovery.

## 1. Global Structure

Internally, Brimley stores arguments in an `arguments` object that may include:

| **Key**      | **Type** | **Description**                                                                                                                               |
| ------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_ref` | `string` | A reference to a named Entity (e.g., `User`). Inherits all properties of that Entity as arguments.  The Entity must be dictionary-compatable. |
| `inline`     | `dict`   | Manual argument definitions. Supports **Shorthand**, **Complex**, or **JSON Schema** modes.                                                   |

For Python functions, this structure is typically inferred from type hints and `Annotated` metadata.

---

## 2. The `inline` Argument Modes

The Brimley parser determines the complexity of the arguments based on the "fingerprint" of the `inline` dictionary.

### A. Shorthand Mode (Type-only)

- **Trigger:** Values are primitive type strings.
- **Use Case:** Quick scripts and simple parameters.

```python
from brimley import function

@function
def get_customer(customer_id: int, is_active: bool) -> dict:
    return {"customer_id": customer_id, "is_active": is_active}
```

### B. Complex Mode (Brimley Metadata)

- **Trigger:** Values are dictionaries, but the top-level `inline` key does **not** contain `properties`.
- **Use Case:** Adding defaults, constraints, and descriptions.

```python
from brimley import function

@function
def list_orders(limit: int = 10) -> list[dict]:
    return []
```
### C. Standard Mode (JSON Schema)

- **Trigger:** The `inline` dictionary contains the `properties` key.
- **Use Case:** Strict industry-standard compliance and copy-pasting existing schemas.

```python
from brimley import function

@function(
    arguments={
        "inline": {
            "properties": {"customer_id": {"type": "integer"}},
            "required": ["customer_id"],
        }
    }
)
def get_orders(customer_id: int) -> list[dict]:
    return []
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

```python
from typing import Annotated
from brimley import function, AppState, Config

@function
def audit_action(
    reason: str,
    actor_id: Annotated[str, AppState("user.id")],
    region: Annotated[str, Config("region")],
) -> dict:
    return {"reason": reason, "actor_id": actor_id, "region": region}
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
```python
from typing import Annotated
from brimley import function, AppState

@function
def get_orders(
    customer_id: int,
    status: str = "shipped",
    min_total: float = 0.0,
    user_id: Annotated[str, AppState("user.id")] = "",
) -> list[dict]:
    return []
```

## 7. Resource Path Parameters

When a resource has path parameters, it will require an `arguments` property.  All of the same rules apply.

**Example:** `/docs/{category}/{sub_category}/{doc_index}`
```python
from brimley import function

@function
def get_doc(category: str, sub_category: str, doc_index: int) -> str:
    return f"/{category}/{sub_category}/{doc_index}"
```

#### Handling "Wildcards" (The Catch-all)

If you want to allow a user to pass an arbitrary number of sub-paths (e.g., `/docs/engineering/hardware/sensors/v1`), you should support a **`splat`** or **`remainder`** type:

**Example:** `/docs/{category}/{remainder*}`

```python
from brimley import function

@function
def get_doc_recursive(category: str, remainder: str) -> str:
    return f"/{category}/{remainder}"
```
