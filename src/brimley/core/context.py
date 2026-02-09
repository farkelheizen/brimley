from typing import Any, Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from brimley.core.entity import Entity

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
    # Config is initialized via environment variables by default
    config: Settings = Field(default_factory=Settings)
    
    # Application State: Mutable storage for request/session data
    app: Dict[str, Any] = Field(default_factory=dict)
    
    # Function Registry: Lookup for available functions (Phase 2)
    # Using Any for now to avoid circular imports or Pydantic strictness issues with custom classes
    # Ideally this is 'Registry'
    functions: Any = Field(default_factory=dict)
    
    # Database Manager: Registry of SQL connection pools (Phase 2)
    databases: Dict[str, Any] = Field(default_factory=dict)
