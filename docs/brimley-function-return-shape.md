# Brimley Function Return Shape Specification

> Version 0.5

This specification defines the syntax and validation rules for **Brimley Function Return Shapes**, used to define the expected output structure for Functions (SQL, API, Python).

## 1. Global Structure

The `return_shape` property is polymorphic. It can be defined as a **String** (Shorthand) or a **Dictionary** (Structured).

|**Format**|**Type**|**Description**|
|---|---|---|
|**Shorthand String**|`string`|A single type string (primitive, entity, or collection).|
|**Structured Object**|`dict`|A dictionary containing `entity_ref` and/or `inline` keys.|

## 2. Shorthand String Mode

When `return_shape` is a string, Brimley parses it as a root-level type. This is the most common format for SQL and Python functions. In Python, this is typically inferred from return type annotations.

### A. Primitive Returns

Used for functions that return a single scalar value.

- `return_shape: void` (Explicitly returns nothing)
    
- `return_shape: string`
    
- `return_shape: int`
    
- `return_shape: bool`

Python examples:

```python
from brimley import function

@function
def ping() -> str:
  return "pong"

@function
def get_count() -> int:
  return 42
```
    

### B. Entity and Collection Returns

Used for functions returning mapped objects or lists of objects.

- `return_shape: Order` (Returns a single object matching the `Order` Entity)
    
- `return_shape: Order[]` (Returns a list of `Order` Entities; common for SELECT statements)
    
- `return_shape: string[]` (Returns a list of raw strings)

Python examples:

```python
from pydantic import BaseModel
from brimley import function

class Order(BaseModel):
  id: int
  status: str

@function
def get_order(order_id: int) -> Order:
  return Order(id=order_id, status="shipped")

@function
def list_orders() -> list[Order]:
  return [Order(id=1, status="shipped")]
```
    

## 3. Structured Object Mode

When returning complex, nested data or adding metadata (like descriptions) to the output fields, use the Object format.

|**Key**|**Type**|**Description**|
|---|---|---|
|`entity_ref`|`string`|A reference to a named Entity. The return shape inherits that schema.|
|`inline`|`dict`|`str`|

### A. Inline Shorthand (Type-only)

- **Trigger:** `inline` values are primitive type strings.
    

```
return_shape:
  inline:
    order_id: int
    is_valid: bool
```

Decorator example with explicit structured shape:

```python
from brimley import function

@function(return_shape={"inline": {"order_id": "int", "is_valid": "bool"}})
def validate_order(order_id: int) -> dict:
    return {"order_id": order_id, "is_valid": True}
```

### B. Inline Complex (Brimley Metadata)

- **Trigger:** `inline` values are dictionaries.
    

```
return_shape:
  inline:
    revenue:
      type: decimal
      description: "Total calculated revenue"
```

Decorator example:

```python
from brimley import function

@function(
  return_shape={
    "inline": {
      "revenue": {"type": "decimal", "description": "Total calculated revenue"}
    }
  }
)
def revenue_summary() -> dict:
  return {"revenue": 10.5}
```

## 4. Void and Omitted Shapes

- **Explicit Void:** `return_shape: void`. Tells the framework and LLM that no data is returned.
    
- **Omitted:** If `return_shape` is missing entirely (common in SQL UPDATE statements), it defaults to **void**.
    

## 5. Summary Table of Syntax

|**Requirement**|**Syntax**|
|---|---|
|Returns nothing|`return_shape: void`|
|Returns a list of strings|`return_shape: string[]`|
|Returns a list of database rows|`return_shape: MyEntity[]`|
|Returns a wrapped object|`return_shape: { inline: { data: MyEntity[], count: int } }`|

Python annotation equivalents:

- `def noop() -> None` -> `void`
- `def names() -> list[str]` -> `string[]`
- `def order() -> Order` -> `Order`
- `def orders() -> list[Order]` -> `Order[]`

> [!TIP]
> 
> **SQL Functions:** Always use `MyEntity[]` when your SELECT statement returns multiple rows that match a defined Entity schema.

## 6. Runtime Marshaling

Brimley employs a **Result Mapper** at runtime to ensure the output of a function matches the contract defined in `return_shape`.

1. **Scalar Marshaling**: If a function returns a primitive (e.g., `int`) but the implementation returns a string "123", Brimley attempts to cast it.
    
2. **Entity Marshaling**:
    
    - If `return_shape` references an Entity (e.g., `Order`), Brimley looks up the `Order` definition in the registry.
        
    - It validates the raw output (e.g., a database row dict) against the Entity's schema.
        
    - **Strictness**: Missing required fields in the output will raise a runtime error. Extra fields in the output are generally ignored (depending on Entity configuration).
        
3. **Collection Handling**:
    
    - If `return_shape` ends in `[]` (e.g., `Order[]`), Brimley expects an iterable (List) of items.
        
    - It iterates over the raw list and validates each item against the target Entity.