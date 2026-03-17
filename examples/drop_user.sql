/*
---
name: drop_user
type: sql_function
description: Deletes a user with the specified ID.
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
DELETE FROM users
WHERE id = :user_id
RETURNING id, username, email;
