/*
---
name: get_users
type: sql_function
description: Retrieves users ordered by newest first with an optional row limit.
connection: default
return_shape: list[dict]
arguments:
  inline:
    limit:
      type: int
      default: 10
mcp:
  type: tool
---
*/
SELECT id, username, email 
FROM users 
ORDER BY id DESC 
LIMIT :limit
