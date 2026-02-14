/*
---
name: get_users
type: sql_function
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
