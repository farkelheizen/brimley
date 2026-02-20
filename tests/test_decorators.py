from brimley import AppState, Config, Connection, entity, function


def test_function_decorator_supports_bare_form():
    @function
    def greet(name: str) -> str:
        return f"Hello {name}"

    meta = getattr(greet, "_brimley_meta")

    assert meta["name"] is None
    assert meta["type"] == "python_function"
    assert meta["reload"] is True
    assert meta["extra"] == {}


def test_function_decorator_supports_configured_form():
    @function(name="welcome", mcpType="tool", reload=False, type="sql_function", description="desc")
    def greet(name: str) -> str:
        return f"Hello {name}"

    meta = getattr(greet, "_brimley_meta")

    assert meta["name"] == "welcome"
    assert meta["type"] == "sql_function"
    assert meta["reload"] is False
    assert meta["mcpType"] == "tool"
    assert meta["extra"] == {"description": "desc"}


def test_entity_decorator_supports_bare_form():
    @entity
    class User:
        pass

    meta = getattr(User, "_brimley_meta")

    assert meta["name"] is None
    assert meta["type"] == "python_entity"
    assert meta["description"] is None
    assert meta["extra"] == {}


def test_entity_decorator_supports_configured_form():
    @entity(name="UserRecord", description="entity desc", tag="core")
    class User:
        pass

    meta = getattr(User, "_brimley_meta")

    assert meta["name"] == "UserRecord"
    assert meta["type"] == "python_entity"
    assert meta["description"] == "entity desc"
    assert meta["extra"] == {"description": "entity desc", "tag": "core"}


def test_top_level_imports_remain_available():
    app_state = AppState("foo")
    config = Config("bar")

    assert app_state.key == "foo"
    assert config.key == "bar"
    assert Connection.__name__ == "Connection"
