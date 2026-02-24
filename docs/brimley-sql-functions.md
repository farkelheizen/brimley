# Brimley SQL Functions

> Version 0.4
SQL Functions in Brimley allow developers to expose database queries as Tools or internal logic. They support metadata blocks embedded directly within `.sql` files.

## 1. Core Properties

|**Property**|**Type**|**Required**|**Description**|
|---|---|---|---|
|`name`|string|Yes|The unique identifier for the tool.|
|`type`|string|Yes|Always `sql_function`.|
|`connection`|string|No|The name of the managed database pool. Defaults to `default`. |
|`handler`|string|Conditional|Used in YAML definitions to point to a `.sql` file. |
|`description`|string|No|Metadata describing the query's purpose for LLMs. |
|`args`|dict|No|Maps named SQL parameters (e.g., `:id`) to types and sources. See [arguments](brimley-function-arguments.md). |
|`return_shape`|dict|No|Defines the structure of the row results.  If ommitted, the function is treated as `void`. See [return shape](brimley-function-return-shape.md). |

## 2. Defining Functions in `.sql` Files

The preferred method for defining a SQL function is to place a YAML frontmatter block inside a comment at the top of a `.sql` file.

### YAML Delimiters

To ensure clean parsing, the YAML metadata **must** be enclosed within triple-dash delimiters (`---`) inside the SQL comment block.

```
/*
---
name: get_customer_orders
type: sql_function
connection: analytics_db
description: "Retrieves all orders for a specific customer, filtered by status."
args:
  inline:
    customer_id: int
    status: string
return_shape:
  entity_ref: User[]
---
*/

SELECT 
    order_id, 
    amount, 
    status, 
    created_at
FROM orders
WHERE customer_id = :customer_id
  AND status = :status;
```

**Update example:**

```
/*
---
name: update_user_status
type: sql_function
description: "Updates a user's status in the system."
connection: default  # Maps to a key in brimley.yaml
args:
  inline:
    user_id: int
    new_status: string
---
*/

UPDATE users 
SET status = :new_status, 
    updated_at = CURRENT_TIMESTAMP
WHERE id = :user_id;
```

## 3. Arguments & State Injection

SQL functions cannot access `context.app` directly. To use dynamic values (like the current User ID) in your query, you must map them in the `args` block using `from_context`.

```
args:
  inline:
    user_id:
      type: int
      from_context: "app.user.id" # Mapped automatically by the runner
```

```
SELECT * FROM orders WHERE user_id = :user_id
```

## 4. Named Parameters

Brimley uses **colon-prefixed** named parameters (e.g., `:parameter_name`) supported by SQLAlchemy.

1. **Mapping:** The keys defined in the `args.inline` or `args.entity_ref` block must match the parameter names used in the SQL body.
    
2. **Injection Security:** Brimley utilizes parameterized queries (prepared statements) to prevent SQL injection. Values are passed as bound variables rather than string concatenation.  **Do not** use string formatting or f-strings in your SQL, as this leads to SQL injection vulnerabilities.
    

## 5. Connection Management

The `connection` property determines which database resource the query executes against.

- **Default Behavior:** If `connection` is omitted, Brimley defaults to the connection named `default` in the context.
    
- **Registry:** Connection names must correspond to the keys available in `context.databases`.

## 6. Result Sets and Return Shapes

SQL functions typically return an array of objects (rows).

### Entity Auto-Mapping

If a `return_shape` uses an `entity_ref` (e.g., `User` or `User[]`), Brimley automatically maps raw database rows to that entity.

In 0.4, these entities are expected to be Python-based entities discovered from decorated classes (for example `@entity(name="User")`).

1. **Column Matching:** The columns returned by your SQL `SELECT` statement must match the fields defined in the Entity.
    
2. **Aliasing:** Use SQL `AS` aliases to match Pydantic field names if the database schema differs (e.g., `SELECT user_id AS id`).
    
3. **Validation:** The framework will raise a runtime error if the database result cannot be coerced into the defined Entity (e.g., missing required fields).
    
    

> [!TIP]
> 
> **Column Aliasing:** Use `AS` in your SQL to ensure the output keys match your `return_shape` definition exactly (e.g., `SELECT user_id AS id`).