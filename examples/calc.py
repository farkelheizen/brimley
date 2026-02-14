"""
---
name: calculate_tax
type: python_function
return_shape: float
handler: calculate_tax
arguments:
  inline:
    amount: float
    rate: float
mcp:
  type: tool
---
"""
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
