/*
---
name: update_user
type: sql_function
description: Updates a user's details with the specified information.
connection: default
return_shape: dict
arguments:
  inline:
    user_id:
      type: str
    username:
      type: str
    email:
      type: str
mcp:
  type: tool
---
*/
UPDATE users
SET username = :username, email = :email
WHERE id = :user_id
RETURNING id, username, email;
    