from typing import Any

from brimley import function


class Context:
    pass


Context.__module__ = "mcp.server.fastmcp"


@function(name="agent_sample", mcpType="tool")
async def agent_sample(prompt: str, mcp_ctx: Context) -> dict:
    if hasattr(mcp_ctx, "sample"):
        sample = await mcp_ctx.sample(messages=prompt)
        sample_text = sample.text if hasattr(sample, "text") else str(sample)
        model = getattr(sample, "model", "fastmcp")
        stop_reason = getattr(sample, "stop_reason", "complete")
    else:
        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]
        sample = mcp_ctx.session.sample(messages=messages)
        sample_text = sample.message.content[0].text
        model = sample.model
        stop_reason = sample.stop_reason
    
    return {
        "prompt": prompt,
        "sample_text": sample_text,
        "model": model,
        "stop_reason": stop_reason,
    }
