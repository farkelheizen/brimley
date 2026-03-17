/*
---
name: add_user
type: sql_function
description: Creates a new user with the specified details.
connection: default
return_shape: dict
arguments:
  inline:
    username:
      type: str
    email:
      type: str
mcp:
  type: tool
---
*/
INSERT INTO users (username, email)
VALUES (:username, :email)
RETURNING id, username, email;
