# Brimley Functions
> Version 0.2

Brimley functions are defined in files that are scanned at start time.  

## Core Properties

All functions share core properties.

| **Property**      | **Type**        | **Required** | **Description**                                                                 |
| ----------------- | --------------- | ------------ | ------------------------------------------------------------------------------- |
| `name`            | string          | Yes          | Unique function name. See [naming conventions](brimley-naming-conventions.md). |                                                                               |
| `type`            | string          | Yes          | Indicates the type of function.                                                     |
| `description`     | string          | No           |                                                                                 |
| `arguments`       | dict            | No           | See [arguments](brimley-function-arguments.md). |        
| `return_shape`    | string \| dict  | Yes          | See [return shape](brimley-function-return-shape.md). |                             |

## Types of Functions

| **Function Type** | **File Extension(s)** | **Description** |
| -- | -- | -- |
| [Template Functions](brimley-template-functions.md) | *.yaml, *.md | Used to define strings or a list of messages based upon the arguments and an internal template |
| [Python Functions](brimley-python-functions.md) | *.py | TBD |
| [SQL Functions](brimley-sql-functions.md) | *.sql | TBD |

