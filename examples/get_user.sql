/*
---
name: get_user
type: sql_function
description: Retrieves a user by ID.
connection: default
return_shape: dict
arguments:
  inline:
    user_id:
      type: str
mcp:
  type: tool
---
*/
SELECT id, username, email
FROM users
WHERE id = :user_id;
