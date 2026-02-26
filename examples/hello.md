---
# Version 0.5
name: hello
type: template_function
description: Renders a friendly welcome message using a provided name and support email.
return_shape: string
arguments:
  inline:
    name:
      type: string
      default: "World"
    support_email:
      type: string
      from_context: "config.support_email"
mcp:
  type: tool
---
# Hello {{ args.name }}!

Welcome to Brimley.

Contact us at: {{ args.support_email }}
