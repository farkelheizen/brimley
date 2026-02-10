from typing import NewType

# Placeholder for future connection object
# In the future this might be a SQLAlchemy session or similar
Connection = NewType("Connection", object)

class AppState:
    """
    Marker for Dependency Injection to request a value from context.app.
    Usage: Annotated[T, AppState("key")]
    """
    def __init__(self, key: str):
        self.key = key

    def __repr__(self):
        return f"AppState('{self.key}')"
    
    def __eq__(self, other):
        return isinstance(other, AppState) and self.key == other.key
    
    def __hash__(self):
        return hash(self.key)

class Config:
    """
    Marker for Dependency Injection to request a value from context.config.
    Usage: Annotated[T, Config("key")]
    """
    def __init__(self, key: str):
        self.key = key
        
    def __repr__(self):
        return f"Config('{self.key}')"

    def __eq__(self, other):
        return isinstance(other, Config) and self.key == other.key
    
    def __hash__(self):
        return hash(self.key)
