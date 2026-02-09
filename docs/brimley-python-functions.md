# Brimley Python Functions
> Version 0.2

Python Functions in Brimley allow developers to execute complex logic, perform data transformations, and interact with external systems using native Python code. These functions benefit from **Reflection-Driven Schema Generation**, where Brimley automatically derives the input schema from Python type hints.

## 1. Core Properties

|**Property**|**Type**|**Required**|**Description**|
|---|---|---|---|
|`name`|string|Yes|The unique identifier for the function.|
|`type`|string|Yes|Always `python_function`.|
|`handler`|string|Conditional|The dot-notation path to the Python function (e.g., `pkg.module.func`).|
|`description`|string|No|A docstring or explicit description for LLM discovery.|
|`arguments`|dict|No|Inferred via reflection by default; can be overridden.|
|`return_shape`|dict|No|Defines the output structure.|

## 2. Registration Methods

### A. The `@brimley_function` Decorator

The most common way to define a function is within Python code. When a function is decorated, the `handler` is **inferred** automatically by the framework.

```
from typing import List
from brimley import brimley_function, BrimleyContext

@brimley_function(name="process_batch")
def process_batch(context: BrimleyContext, ids: List[int]):
    """Processes a batch of record IDs."""
    db = context.databases["default"]
    # ... logic ...
    return {"count": len(ids)}
```

### B. YAML Definition

You can register existing Python functions (or third-party library functions) via a `.yaml` file. In this mode, the `handler` is **required** to serve as a pointer to the code.

```
name: calculate_risk
type: python_function
handler: analytics_engine.risk.calculate
description: "Calculates risk score for a specific profile"
arguments:
  inline:
    profile_id: int
    strict_mode: bool
```

## 3. The `handler` Property

The `handler` string represents the fully qualified name of the Python function.

- **Inference:** When using the decorator, Brimley captures the module and function name at runtime. You do not need to provide it in the decorator arguments.
    
- **Explicit Mapping:** In YAML, the handler must be importable by the Brimley runner. If the function is located in `services/math.py` and the function is named `add`, the handler is `services.math.add`.
    

## 4. The `BrimleyContext` Injection

By convention, the **first argument** of any Brimley Python function is reserved for the [BrimleyContext](brimley-context.md).

1. **Framework Injection:** The runner automatically injects the active context into this slot.
    
2. **Schema Exclusion:** When generating JSON schemas for LLM Tools or MCP, Brimley **omits** the `context` argument. The LLM never sees or attempts to provide a value for it.
    
3. **Access:** Use this to access `config`, `databases`, or call other `functions` registered in the system.
    

## 5. Reflection & Type Mapping

Brimley maps standard Python type hints to JSON Schema types to facilitate tool-calling.

|**Python Type**|**JSON Schema Equivalent**|**Note**|
|---|---|---|
|`int`|`integer`||
|`float` / `Decimal`|`number`||
|`bool`|`boolean`||
|`str`|`string`||
|`List[T]`|`array`|See [collection support](brimley-function-arguments.md#collection-support)|
|`Optional[T]`|`T`|Property is marked as "not required"|
|`Enum`|`string`|Uses the Enum members as `enum` values|
