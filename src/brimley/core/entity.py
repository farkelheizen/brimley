from typing import Any, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, model_validator

class Entity(BaseModel):
    """Base class for all Brimley domain entities."""
    model_config = ConfigDict(extra="forbid")

class ContentBlock(Entity):
    """An atomic block of content (text or image) for multimodal messages."""
    type: Literal["text", "image"]
    text: Optional[str] = None
    data: Optional[str] = None
    mimeType: Optional[str] = None

    @model_validator(mode='after')
    def validate_content_fields(self) -> 'ContentBlock':
        if self.type == "text":
            if not self.text:
                raise ValueError("Field 'text' is required when type is 'text'")
        elif self.type == "image":
            if not self.data:
                raise ValueError("Field 'data' is required when type is 'image'")
            if not self.mimeType:
                raise ValueError("Field 'mimeType' is required when type is 'image'")
        return self

class PromptMessage(Entity):
    """A universal MCP message (supports both simple text and multimodal)."""
    role: Literal["user", "assistant", "system"]
    content: Union[str, List[ContentBlock]]
