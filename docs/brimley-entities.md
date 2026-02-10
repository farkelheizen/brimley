# Brimley Entities

> Version 0.2

Entities are the data structures and domain models within a Brimley application. They are used to define the shape of inputs and outputs for functions, as well as the structure of the application context.

All Entities in Brimley inherit from `pydantic.BaseModel`.

## Built-In Entities

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

## User-Defined Entities

Users can define their own Entities by creating `.yaml` files in the project structure. These entities are discovered at startup and added to the Entity Registry.

### File Format

A user-defined entity file must start with `type: entity`.

**Example: `src/models/customer.yaml`**

```
type: entity
name: Customer
description: "Represents a customer in the system."
fields:
  id:
    type: string
    description: "Unique identifier"
  email:
    type: string
    pattern: "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
  tier:
    type: string
    default: "free"
    enum: ["free", "pro", "enterprise"]
```

These definitions are parsed and converted into Pydantic models at runtime, accessible via `ctx.entities.get("Customer")`.