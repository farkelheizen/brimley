"""
---
name: nested_greeting
type: python_function
return_shape: string
handler: nested_greeting
arguments:
  inline:
    name: string
---
"""
from brimley.core.context import BrimleyContext


def nested_greeting(name: str, ctx: BrimleyContext) -> str:
    return ctx.execute_function_by_name(
        function_name="hello",
        input_data={"name": name},
    )
