/*
---
name: list_startup_events
type: sql_function
description: Lists schema initialization events written by the Oracle startup hook.
connection: default
return_shape: list[dict]
mcp:
  type: tool
---
*/
SELECT event_id, event_name, details, created_at
FROM brimley_demo_startup_events
ORDER BY event_id DESC