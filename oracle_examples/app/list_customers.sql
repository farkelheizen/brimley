/*
---
name: list_customers
type: sql_function
description: Lists the demo Oracle customers created by the startup hook.
connection: default
return_shape: list[dict]
mcp:
  type: tool
---
*/
SELECT customer_id, email, full_name, status, created_at
FROM brimley_demo_customers
ORDER BY customer_id