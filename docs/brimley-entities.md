# Brimley Entities

> Version 0.3

Entities are the data structures and domain models in a Brimley application. In 0.3, entities are Python-first and discovered from decorated classes.

## 1. Entity Definition Model (0.3)

Use `@entity` on Python classes (typically Pydantic models):

```python
from pydantic import BaseModel
from brimley import entity

@entity(name="User")
class User(BaseModel):
  id: int
  username: str
  email: str
```

Supported decorator forms:

- `@entity`
- `@entity(...)`

Brimley records metadata for discovery and registers the entity with type `python_entity`.

## 2. YAML Entity Deprecation

YAML-based entity files are deprecated in the 0.3 decorator transition.

- Prefer Python entity classes with `@entity`.
- Existing YAML entity references should be migrated to Python classes.
- Entity discovery for modern workflows is based on Python AST/runtime metadata, not standalone entity YAML definitions.

## 3. Built-In Entities

Brimley comes with several core entities pre-loaded into the registry.

### ContentBlock and Prompt Message

These are used to define the output of [template functions](brimley-template-functions.md).
```
ContentBlock:
  type: object
  description: "An atomic block of content (text or image) for multimodal messages."
  properties:
    type:
      type: string
      enum: ["text", "image"]
    text:
      type: string
      description: "Required if type is 'text'."
    data:
      type: string
      description: "Base64 image data. Required if type is 'image'."
    mimeType:
      type: string
      description: "MIME type (e.g. 'image/png'). Required if type is 'image'."

PromptMessage:
  type: object
  description: "A universal MCP message (supports both simple text and multimodal)."
  properties:
    role:
      type: string
      enum: ["user", "assistant"]
    content:
      oneOf:
        - type: string  # Option A: Simple String
        - type: array   # Option B: List of Blocks (Text + Image)
          items:
            entity_ref: ContentBlock
```

## 4. Using Entities in Python Functions

Entity classes can be used as return models and validation targets.

### A. Return annotation usage

```python
from pydantic import BaseModel
from brimley import function, entity

@entity(name="User")
class User(BaseModel):
    id: int
    username: str

@function
def get_user(user_id: int) -> User:
    return User(id=user_id, username="alice")
```

### B. Inter-function composition

```python
from brimley import function
from brimley.core.context import BrimleyContext

@function
def get_profile_summary(user_id: int, ctx: BrimleyContext) -> dict:
    user = ctx.execute_function_by_name("get_user", {"user_id": user_id})
    return {"id": user.id, "username": user.username}
```

## 5. Registry and Mapping Behavior

Brimley stores discovered entities in `context.entities`.

- For Python entities, discovery records `python_entity` metadata with a module/class handler.
- Result mapping resolves the registered entity and validates mapped output against the resolved class.
- Built-in entities (`ContentBlock`, `PromptMessage`) remain available by default.

See also [Python Functions](brimley-python-functions.md) and [Return Shapes](brimley-function-return-shape.md).