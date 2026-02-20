from brimley import function


@function(name="calculate_tax", mcpType="tool")
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate
