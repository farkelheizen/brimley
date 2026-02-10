from typing import Any, Dict, Optional
from pydantic import Field, ConfigDict
from brimley.core.entity import Entity, ContentBlock, PromptMessage
from brimley.core.registry import Registry
from brimley.core.models import BrimleyFunction, FrameworkSettings, AppConfig

class BrimleyContext(Entity):
    """
    The central execution context injected into every function.
    """
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    
    # Framework Settings (Maps to 'brimley' section)
    settings: FrameworkSettings = Field(default_factory=FrameworkSettings)
    
    # Application Config (Maps to 'config' section)
    config: AppConfig = Field(default_factory=AppConfig)
    
    # Application State: Mutable storage for request/session data
    app: Dict[str, Any] = Field(default_factory=dict)
    
    # Function Registry: Lookup for available functions
    functions: Registry[BrimleyFunction] = Field(default_factory=Registry)
    
    # Entity Registry: Lookup for domain models and data schemas
    entities: Registry[Entity] = Field(default_factory=Registry)
    
    # Database Definitions (Maps to 'databases' section)
    databases: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None, **data: Any):
        """
        Initialize the context, optionally with a configuration dictionary.
        """
        if config_dict:
            # Seed fields from config_dict if not explicitly provided in data
            if 'settings' not in data:
                data['settings'] = FrameworkSettings(**config_dict.get('brimley', {}))
            if 'config' not in data:
                data['config'] = AppConfig(**config_dict.get('config', {}))
            if 'app' not in data:
                data['app'] = config_dict.get('state', {})
            if 'databases' not in data:
                data['databases'] = config_dict.get('databases', {})
        
        super().__init__(**data)

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
