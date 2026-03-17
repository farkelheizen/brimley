from brimley import function
from loguru import logger

class Context:
    pass

Context.__module__ = "mcp.server.fastmcp"

@function(name="agent_sample", mcpType="tool")
async def agent_sample(prompt: str, mcp_ctx: Context) -> str:
    """Samples a model response from the provided prompt using MCP context."""
    logger.info("Sampling model response for prompt: {}", prompt)
    sample = await mcp_ctx.sample(messages=prompt)
    sample_text = sample.text
    logger.debug("Received sample response length: {}", len(sample_text))
    #model = getattr(sample, "model", "fastmcp")
    #stop_reason = getattr(sample, "stop_reason", "complete")
    return sample_text
