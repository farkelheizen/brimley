/*
---
name: get_users
type: sql_function
connection: analytics_db
return_shape: list[dict]
arguments:
  inline:
    limit:
      type: int
      default: 10
---
*/
SELECT id, username, email 
FROM users 
ORDER BY created_at DESC 
LIMIT {{ args.limit }}
