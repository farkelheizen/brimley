from typing import NewType, Union

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


class Depends:
    """
    Marker that injects a provider's resolved value into a ``@function``
    argument at execution time.

    Usage::

        @function(name="fetch_data")
        async def fetch_data(
            url: str,
            client: httpx.AsyncClient = Depends(get_http_client),
        ):
            ...

    The argument to ``Depends`` is the provider callable (or its string name).
    At AST-scan time the scanner extracts the string name; at runtime the
    ``BrimleyContainer`` resolves the named provider and injects its value.

    ``Depends``-marked parameters are hidden from CLI / REPL / MCP argument
    schemas and must not be supplied by callers.

    Introduced in Brimley 0.8.
    """

    def __init__(self, dependency: Union[str, object]) -> None:
        if callable(dependency):
            self.provider_name: str = dependency.__name__
        elif isinstance(dependency, str):
            self.provider_name = dependency
        else:
            raise TypeError(
                "Depends() requires a callable provider function or a provider name string; "
                f"got {type(dependency)!r}."
            )
        self._dependency = dependency

    def __repr__(self) -> str:
        return f"Depends({self.provider_name!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Depends) and self.provider_name == other.provider_name

    def __hash__(self) -> int:
        return hash(self.provider_name)
