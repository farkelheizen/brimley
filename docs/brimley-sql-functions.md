# Brimley SQL Functions
> Version 0.2

SQL Functions in Brimley allow developers to expose database queries as Tools or internal logic. They support advanced metadata definition via YAML blocks embedded directly within `.sql` files or via standalone `.yaml` definition files.

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
  entity_ref: Order[]
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

## 3. Named Parameters

Brimley uses **colon-prefixed** named parameters (e.g., `:parameter_name`).

1. **Mapping:** The keys defined in the `args.inline` or `args.entity_ref` block must match the parameter names used in the SQL body.
    
2. **Injection Security:** Brimley utilizes parameterized queries (prepared statements) to prevent SQL injection. Values are passed as bound variables rather than string concatenation.
    
3. **Complex Logic:** You can use these parameters anywhere a standard SQL variable is allowed (e.g., `LIMIT :limit_count` or `OFFSET :offset`).
    

## 4. Connection Management

The `connection` property determines which database resource the query executes against.

- **Default Behavior:** If `connection` is omitted, Brimley defaults to the connection named `default` in the context.
    
- **Registry:** Connection names must correspond to the keys available in `context.databases`.
    

## 5. Result Sets and Return Shapes

SQL functions typically return an array of objects (rows).

- **Entity Mapping:** If a `return_shape` uses an `entity_ref` with the `[]` suffix (e.g., `Order[]`), Brimley automatically maps the column names from the `SELECT` statement to the Entity properties.
    
- **Anonymous Sets:** If no `return_shape` is provided, Brimley returns a list of dictionaries where keys are the column aliases.
    

> [!TIP]
> 
> **Column Aliasing:** Use `AS` in your SQL to ensure the output keys match your `return_shape` definition exactly (e.g., `SELECT user_id AS id`).