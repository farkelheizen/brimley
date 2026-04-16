/*
---
name: get_customer_by_email
type: sql_function
description: Retrieves one demo Oracle customer by email address.
connection: default
return_shape: dict
arguments:
  inline:
    email:
      type: string
mcp:
  type: tool
---
*/
SELECT customer_id, email, full_name, status, created_at
FROM brimley_demo_customers
WHERE email = :email