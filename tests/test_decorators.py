from brimley import AppState, Config, Connection, Depends, entity, function, on_shutdown, on_startup, provider


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


# ---------------------------------------------------------------------------
# @provider decorator
# ---------------------------------------------------------------------------


def test_provider_decorator_bare_form():
    @provider
    def get_client():
        pass

    meta = getattr(get_client, "_brimley_meta")
    assert meta["type"] == "provider"
    assert meta["name"] is None
    assert meta["scope"] == "singleton"
    assert meta["eager"] is False


def test_provider_decorator_configured_scope_request():
    @provider(scope="request")
    def get_session():
        pass

    meta = getattr(get_session, "_brimley_meta")
    assert meta["type"] == "provider"
    assert meta["scope"] == "request"
    assert meta["eager"] is False
    assert meta["name"] is None


def test_provider_decorator_configured_with_name_and_eager():
    @provider(name="http_client", scope="singleton", eager=True)
    def get_http_client():
        pass

    meta = getattr(get_http_client, "_brimley_meta")
    assert meta["type"] == "provider"
    assert meta["name"] == "http_client"
    assert meta["scope"] == "singleton"
    assert meta["eager"] is True


def test_provider_decorator_with_generator_function():
    @provider(scope="singleton")
    def get_db():
        conn = object()
        yield conn

    meta = getattr(get_db, "_brimley_meta")
    assert meta["type"] == "provider"
    assert meta["scope"] == "singleton"


def test_provider_decorator_with_async_function():
    @provider
    async def get_async_client():
        pass

    meta = getattr(get_async_client, "_brimley_meta")
    assert meta["type"] == "provider"


def test_provider_decorator_does_not_alter_function_behavior():
    @provider
    def compute():
        return 42

    assert compute() == 42


# ---------------------------------------------------------------------------
# @on_startup decorator
# ---------------------------------------------------------------------------


def test_on_startup_decorator_bare_form():
    @on_startup
    def init_db():
        pass

    meta = getattr(init_db, "_brimley_meta")
    assert meta["type"] == "on_startup"


def test_on_startup_decorator_callable_form():
    @on_startup()
    def init_cache():
        pass

    meta = getattr(init_cache, "_brimley_meta")
    assert meta["type"] == "on_startup"


def test_on_startup_decorator_with_async_function():
    @on_startup
    async def init_async():
        pass

    meta = getattr(init_async, "_brimley_meta")
    assert meta["type"] == "on_startup"


def test_on_startup_decorator_does_not_alter_function_behavior():
    @on_startup
    def warmup():
        return "ready"

    assert warmup() == "ready"


# ---------------------------------------------------------------------------
# @on_shutdown decorator
# ---------------------------------------------------------------------------


def test_on_shutdown_decorator_bare_form():
    @on_shutdown
    def close_connections():
        pass

    meta = getattr(close_connections, "_brimley_meta")
    assert meta["type"] == "on_shutdown"


def test_on_shutdown_decorator_callable_form():
    @on_shutdown()
    def flush_cache():
        pass

    meta = getattr(flush_cache, "_brimley_meta")
    assert meta["type"] == "on_shutdown"


def test_on_shutdown_decorator_with_async_function():
    @on_shutdown
    async def teardown():
        pass

    meta = getattr(teardown, "_brimley_meta")
    assert meta["type"] == "on_shutdown"


def test_on_shutdown_decorator_does_not_alter_function_behavior():
    @on_shutdown
    def cleanup():
        return "done"

    assert cleanup() == "done"


# ---------------------------------------------------------------------------
# Depends import via top-level package
# ---------------------------------------------------------------------------


def test_depends_importable_from_brimley():
    d = Depends("my_provider")
    assert d.provider_name == "my_provider"


# ---------------------------------------------------------------------------
# @function task parameter (B09-S4)
# ---------------------------------------------------------------------------


def test_function_decorator_task_parameter_stored_in_meta():
    @function(name="my_task", task={"interval": "5m"})
    async def my_task():
        pass

    meta = getattr(my_task, "_brimley_meta")
    assert meta["task"] == {"interval": "5m"}


def test_function_decorator_task_full_config():
    @function(
        name="reconciler",
        task={
            "interval": "1m",
            "immediate": True,
            "retries": 3,
            "retry_interval": "5s exponential",
        },
    )
    async def reconciler():
        pass

    meta = getattr(reconciler, "_brimley_meta")
    assert meta["task"]["interval"] == "1m"
    assert meta["task"]["immediate"] is True
    assert meta["task"]["retries"] == 3
    assert meta["task"]["retry_interval"] == "5s exponential"


def test_function_decorator_without_task_has_no_task_key():
    @function(name="plain_func")
    def plain():
        pass

    meta = getattr(plain, "_brimley_meta")
    assert "task" not in meta


def test_function_decorator_task_none_not_stored():
    @function(name="plain_func2", task=None)
    def plain2():
        pass

    meta = getattr(plain2, "_brimley_meta")
    assert "task" not in meta
