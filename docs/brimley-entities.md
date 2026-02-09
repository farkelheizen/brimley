# Brimley Entities
> Version 0.2

## Built-In Entities

### ContentBlock and Prompt Message

These are used to define the output of [template functions](brimley-template-functions.md).

```YAML
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