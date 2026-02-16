from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockMCPTextContent:
    """
    Mock text content block used in mock sampling responses.
    """

    type: str = "text"
    text: str = ""


@dataclass
class MockMCPMessage:
    """
    Mock assistant message returned by mock MCP sampling.
    """

    role: str = "assistant"
    content: list[MockMCPTextContent] = field(default_factory=list)


@dataclass
class MockMCPSampleResult:
    """
    Mock result payload modeled after the shape returned by MCP sampling.
    """

    model: str
    stop_reason: str
    message: MockMCPMessage


class MockMCPSession:
    """
    Lightweight MCP session shim for local invocation and testing.
    """

    def __init__(self, response_text: str = "Mock response from Brimley", model: str = "mock-model") -> None:
        self.response_text = response_text
        self.model = model
        self.sample_calls: list[dict[str, Any]] = []

    def sample(self, *args: Any, **kwargs: Any) -> MockMCPSampleResult:
        """
        Simulate MCP sampling by printing request details and returning a typed dummy response.
        """
        self.sample_calls.append({"args": args, "kwargs": kwargs})

        print("[Mock Sampling]", kwargs if kwargs else args)

        return MockMCPSampleResult(
            model=self.model,
            stop_reason="mock_complete",
            message=MockMCPMessage(
                role="assistant",
                content=[MockMCPTextContent(text=self.response_text)],
            ),
        )


class MockMCPContext:
    """
    Lightweight context shim that exposes a `session.sample` interface.
    """

    def __init__(self, response_text: str = "Mock response from Brimley", model: str = "mock-model") -> None:
        self.session = MockMCPSession(response_text=response_text, model=model)
