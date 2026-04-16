/*
---
name: add_customer
type: sql_function
description: Inserts a demo Oracle customer row.
connection: default
return_shape: dict
arguments:
  inline:
    email:
      type: string
    full_name:
      type: string
    status:
      type: string
mcp:
  type: tool
---
*/
INSERT INTO brimley_demo_customers (email, full_name, status)
VALUES (:email, :full_name, :status)