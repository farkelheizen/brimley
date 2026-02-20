from brimley import function
from brimley.core.context import BrimleyContext


@function(name="nested_greeting")
def nested_greeting(name: str, ctx: BrimleyContext) -> str:
    return ctx.execute_function_by_name(
        function_name="hello",
        input_data={"name": name},
    )
