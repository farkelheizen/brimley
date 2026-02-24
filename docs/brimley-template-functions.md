# Brimley Template Functions

> Version 0.4

Brimley Template Functions are defined in `.md` or `.yaml` files. They exist to generate dynamic strings or prompt messages based on the arguments defined.

## Properties

|**Property**|**Type**|**Required**|**Description**|
|---|---|---|---|
|`name`|string|Yes||
|`type`|string|Yes|Always `template_function`.|
|`description`|string|No||
|`arguments`|dict|No|See [Function Arguments](brimley-function-arguments.md).|
|`return_shape`|string|dict|Yes|
|`template_engine`|string|No|Defaults to `jinja2`.|
|`messages`|PromptMessage[]|No|Defines the messages in the inline YAML. May also be defined in markdown body.|
|`return_shape`|string|Yes|Usually `string` or `markdown`.|

## Template Context & Variables

Templates do **not** have access to the global `BrimleyContext`. They only have access to the arguments defined in their YAML/Frontmatter.

If you need data from the application state (e.g., a User ID or API Key), you must declare it in the `arguments` block using `from_context`.

### Example: Injecting State into a Template

```
name: welcome_email
type: template_function
arguments:
  inline:
    # 1. We declare we need the user_name
    user_name: 
      type: string
      from_context: "app.current_user.name"
---
# 2. We use it simply as a variable
Hello, {{ args.user_name }}!
```

## Examples

### Example 1. Markdown returning messages

After running the body of the markdown file against the arguments using the template engine, the output is parsed into multiple messages with different roles based on the xml tags. This is the default parsing scheme. Brimley will support additional parsing schemes eventually.

```markdown
---
name: creative_writer_prompt
type: template_function
template_engine: jinja2 
arguments:
  genre: string
returns: PromptMessage[]
---

<system>
You are a world-class author specializing in {{ args.genre }}.
Your goal is to help the user expand on their world-building.
</system>

<user>
I have a planet made entirely of glass. How do the inhabitants handle extreme heat?
</user>

<assistant>
That's a fascinating premise. Usually, in glass-based ecosystems, thermal management is handled via...
</assistant>

<user>
Can you give me three specific biological adaptations for this?
</user>
```

### Example 2. Markdown returning a string

```markdown
---
name: list_users
type: template_function
description: generates a user directory
template_engine: jinja2 
arguments:
  genre: string
returns: string
---

### User Directory Total Users: {{ users | length }}

{% for user in users -%}
#### User: {{ user.name }}
* **ID:** {{ user.id }}
* **Role:** {{ user.role | title }}
* **Status:** {{ 'Active' if user.is_active else 'Inactive' }}
* **Contact:** {{ user.email or 'No email provided' }}
  
---
{% endfor %}
```

### Example 3. YAML example returning messages

```YAML
name: creative_writer_prompt
type: template_function
template_engine: jinja2
arguments:
  genre: string
returns: PromptMessage[]
messages:
  - role: system
    content: |
      You are a world-class author specializing in {{ args.genre }}.
      Your goal is to help the user expand on their world-building.

  - role: user
    content: "I have a planet made entirely of glass. How do the inhabitants handle extreme heat?"

  - role: assistant
    content: "That's a fascinating premise. Usually, in glass-based ecosystems, thermal management is handled via..."

  - role: user
    content: "Can you give me three specific biological adaptations for this?"
```