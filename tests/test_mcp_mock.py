from brimley.mcp.mock import (
    MockMCPContext,
    MockMCPMessage,
    MockMCPSampleResult,
    MockMCPSession,
    MockMCPTextContent,
)


def test_mock_mcp_context_exposes_session_sample_interface() -> None:
    context = MockMCPContext()

    assert isinstance(context.session, MockMCPSession)


def test_mock_mcp_session_sample_prints_and_returns_typed_result(capsys) -> None:
    session = MockMCPSession(response_text="agent result", model="local-shim")

    result = session.sample(
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="You are helpful",
    )

    captured = capsys.readouterr()

    assert "[Mock Sampling]" in captured.out
    assert isinstance(result, MockMCPSampleResult)
    assert isinstance(result.message, MockMCPMessage)
    assert isinstance(result.message.content[0], MockMCPTextContent)
    assert result.message.role == "assistant"
    assert result.message.content[0].text == "agent result"
    assert result.model == "local-shim"
    assert result.stop_reason == "mock_complete"
    assert len(session.sample_calls) == 1
    assert session.sample_calls[0]["kwargs"]["system_prompt"] == "You are helpful"
