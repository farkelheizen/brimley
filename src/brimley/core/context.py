from typing import Any, Dict
from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from brimley.core.entity import Entity, ContentBlock, PromptMessage
from brimley.core.registry import Registry
from brimley.core.models import BrimleyFunction

class Settings(BaseSettings):
    """
    Global configuration loaded from environment variables.
    Prefix: BRIMLEY_
    """
    model_config = SettingsConfigDict(env_prefix='BRIMLEY_', env_file='.env', extra='ignore')

    env: str = "development"
    app_name: str = "Brimley App"

class BrimleyContext(Entity):
    """
    The central execution context injected into every function.
    """
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    
    # Config is initialized via environment variables by default
    config: Settings = Field(default_factory=Settings)
    
    # Application State: Mutable storage for request/session data
    app: Dict[str, Any] = Field(default_factory=dict)
    
    # Function Registry: Lookup for available functions
    functions: Registry[BrimleyFunction] = Field(default_factory=Registry)
    
    # Entity Registry: Lookup for domain models and data schemas
    entities: Registry[Entity] = Field(default_factory=Registry)
    
    # Database Manager: Registry of SQL connection pools (Phase 2)
    databases: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """
        Initialize the context, registering built-in entities.
        """
        # Register built-in entities
        # Note: We are registering the classes themselves as they have name attributes
        # and represent the definition of the entity.
        if "ContentBlock" not in self.entities:
            # We ensure they have a name for the registry
            ContentBlock.name = "ContentBlock"
            self.entities.register(ContentBlock) # type: ignore
            
        if "PromptMessage" not in self.entities:
            PromptMessage.name = "PromptMessage"
            self.entities.register(PromptMessage) # type: ignore
