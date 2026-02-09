import pytest
from pydantic import ValidationError
from brimley.core.entity import Entity, ContentBlock, PromptMessage
from brimley.utils.diagnostics import BrimleyDiagnostic

# -----------------------------------------------------------------------------
# Entity Tests
# -----------------------------------------------------------------------------

def test_entity_is_pydantic_model():
    """Verify Entity is a Pydantic model (implies behavior like .model_dump())."""
    class MyEntity(Entity):
        name: str

    e = MyEntity(name="test")
    assert e.model_dump() == {"name": "test"}

# -----------------------------------------------------------------------------
# ContentBlock Tests
# -----------------------------------------------------------------------------

def test_content_block_text_valid():
    """Verify ContentBlock accepts valid text configuration."""
    block = ContentBlock(type="text", text="Hello world")
    assert block.type == "text"
    assert block.text == "Hello world"
    assert block.data is None

def test_content_block_image_valid():
    """Verify ContentBlock accepts valid image configuration."""
    block = ContentBlock(type="image", data="base64str", mimeType="image/png")
    assert block.type == "image"
    assert block.data == "base64str"
    assert block.mimeType == "image/png"
    assert block.text is None

# -----------------------------------------------------------------------------
# PromptMessage Tests
# -----------------------------------------------------------------------------

def test_prompt_message_simple_text():
    """Verify PromptMessage accepts a simple string content."""
    msg = PromptMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"

def test_prompt_message_multimodal():
    """Verify PromptMessage accepts a list of ContentBlocks."""
    blocks = [
        ContentBlock(type="text", text="Look at this"),
        ContentBlock(type="image", data="aaa", mimeType="image/jpeg")
    ]
    msg = PromptMessage(role="user", content=blocks)
    assert msg.role == "user"
    assert len(msg.content) == 2
    assert msg.content[0].text == "Look at this"

# -----------------------------------------------------------------------------
# Diagnostics Tests
# -----------------------------------------------------------------------------

def test_brimley_diagnostic_structure():
    """Verify BrimleyDiagnostic has the required fields."""
    diag = BrimleyDiagnostic(
        file_path="/tmp/test.sql",
        error_code="ERR_TEST",
        message="Something went wrong",
        suggestion="Fix it",
        line_number=10
    )
    assert diag.file_path == "/tmp/test.sql"
    assert diag.error_code == "ERR_TEST"
    assert diag.line_number == 10
    
    # Check string representation contains key info (for reporting)
    str_repr = str(diag)
    assert "ERR_TEST" in str_repr
    assert "/tmp/test.sql" in str_repr
