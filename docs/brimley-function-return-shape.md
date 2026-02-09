# Brimley Function Return Shape Specification
> Version 0.2

This specification defines the syntax and validation rules for **Brimley Function Return Shapes**, used to define the expected output structure for Functions (SQL, API, Python).

## 1. Global Structure

The `return_shape` property is polymorphic. It can be defined as a **String** (Shorthand) or a **Dictionary** (Structured).

| **Format**            | **Type** | **Description**                                            |
| --------------------- | -------- | ---------------------------------------------------------- |
| **Shorthand String**  | `string` | A single type string (primitive, entity, or collection).   |
| **Structured Object** | `dict`   | A dictionary containing `entity_ref` and/or `inline` keys. |

## 2. Shorthand String Mode

When `return_shape` is a string, Brimley parses it as a root-level type. This is the most common format for SQL and Python functions.

### A. Primitive Returns

Used for functions that return a single scalar value.

- `return_shape: void` (Explicitly returns nothing)
    
- `return_shape: string`
    
- `return_shape: int`
    
- `return_shape: bool`
    

### B. Entity and Collection Returns

Used for functions returning mapped objects or lists of objects.

- `return_shape: Order` (Returns a single object matching the `Order` Entity)
    
- `return_shape: Order[]` (Returns a list of `Order` Entities; common for SELECT statements)
    
- `return_shape: string[]` (Returns a list of raw strings)
    

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

### B. Inline Complex (Brimley Metadata)

- **Trigger:** `inline` values are dictionaries.
    

```
return_shape:
  inline:
    revenue:
      type: decimal
      description: "Total calculated revenue"
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

> [!TIP]
> 
> **SQL Functions:** Always use `MyEntity[]` when your SELECT statement returns multiple rows that match a defined Entity schema.