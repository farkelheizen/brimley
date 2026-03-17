from brimley import function
from loguru import logger


@function(name="calculate_tax", mcpType="tool")
def calculate_tax(amount: float, rate: float) -> float:
    """Calculates tax from an amount and rate."""
    logger.info("Calculating tax for amount: {} at rate: {}", amount, rate)
    result = amount * rate
    logger.debug("Tax result: {}", result)
    return result
