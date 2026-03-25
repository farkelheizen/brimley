import pytest
from sqlalchemy import create_engine, text
from brimley.execution.sql_runner import SqlRunner
from brimley.core.models import SqlFunction
from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity

class UserEntity(Entity):
    id: int
    name: str

@pytest.fixture
def engine():
    # In-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"))
        conn.execute(text("INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')"))
        conn.execute(text("INSERT INTO users (id, name, email) VALUES (2, 'Bob', 'bob@example.com')"))
        conn.commit()
    return engine

@pytest.fixture
def runner():
    return SqlRunner()

@pytest.fixture
def context(engine):
    ctx = BrimleyContext()
    ctx.app["user_id"] = 1
    ctx.databases = {"default": engine}
    UserEntity.name = "User"
    ctx.entities.register(UserEntity)
    return ctx

def test_sql_execution_entity_mapping(runner, context):
    func = SqlFunction(
        name="get_users",
        type="sql_function",
        return_shape="User[]",
        sql_body="SELECT id, name FROM users"
    )
    
    result = runner.run(func, {}, context)
    
    assert len(result) == 2
    assert isinstance(result[0], UserEntity)
    assert result[0].name == "Alice"
    assert result[1].name == "Bob"

def test_sql_execution_select(runner, context):
    func = SqlFunction(
        name="get_user",
        type="sql_function",
        return_shape="dict[]",
        sql_body="SELECT id, name FROM users WHERE id = :id",
        arguments={
            "inline": {
                "id": "int"
            }
        }
    )
    
    # Run with explicit argument
    result = runner.run(func, {"id": 1}, context)
    
    assert len(result) == 1
    assert result[0]["name"] == "Alice"
    assert result[0]["id"] == 1

def test_sql_execution_context_injection(runner, context):
    func = SqlFunction(
        name="get_my_profile",
        type="sql_function",
        return_shape="dict[]",
        sql_body="SELECT * FROM users WHERE id = :uid",
        arguments={
            "inline": {
                "uid": {
                    "type": "int",
                    "from_context": "app.user_id"
                }
            }
        }
    )
    
    # Run without explicit argument, relying on context injection
    result = runner.run(func, {}, context)
    
    assert len(result) == 1
    assert result[0]["name"] == "Alice"

def test_sql_execution_insert(runner, context):
    func = SqlFunction(
        name="add_user",
        type="sql_function",
        return_shape="dict",
        sql_body="INSERT INTO users (id, name, email) VALUES (:id, :name, :email)",
        arguments={
            "inline": {
                "id": "int",
                "name": "string",
                "email": "string"
            }
        }
    )
    
    result = runner.run(func, {"id": 3, "name": "Charlie", "email": "charlie@example.com"}, context)
    
    assert result["rows_affected"] == 1
    
    # Verify insertion
    engine = context.databases["default"]
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM users WHERE id = 3")).mappings().one()
        assert res["name"] == "Charlie"

def test_sql_execution_insert_returning_commits(runner, context):
    func = SqlFunction(
        name="add_user_returning",
        type="sql_function",
        return_shape="dict[]",
        sql_body="INSERT INTO users (id, name, email) VALUES (:id, :name, :email) RETURNING id, name",
        arguments={
            "inline": {
                "id": "int",
                "name": "string",
                "email": "string"
            }
        }
    )

    result = runner.run(func, {"id": 4, "name": "Dora", "email": "dora@example.com"}, context)

    assert result == [{"id": 4, "name": "Dora"}]

    engine = context.databases["default"]
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM users WHERE id = 4")).mappings().one()
        assert res["name"] == "Dora"

def test_sql_execution_missing_connection(runner):
    context = BrimleyContext()
    # No databases registered
    
    func = SqlFunction(
        name="fail_test",
        type="sql_function",
        sql_body="SELECT 1",
        connection="missing",
        return_shape="void"
    )
    
    with pytest.raises(RuntimeError, match="Database connection 'missing' not found"):
        runner.run(func, {}, context)

# ---------------------------------------------------------------------------
# B08-S10: Container-based connection resolution
# ---------------------------------------------------------------------------

# SqlRunner instance shared by the container-based tests below
_sql_runner = SqlRunner()


class _MockContainer:
    """Minimal container stub that returns engines by provider name."""

    def __init__(self, providers: dict) -> None:
        self._providers = providers

    def resolve(self, name: str):
        if name not in self._providers:
            from brimley.core.container import ProviderResolutionError
            raise ProviderResolutionError(f"No provider '{name}'")
        return self._providers[name]


def test_sql_runner_uses_container_engine(engine):
    """SqlRunner resolves connection via container when context.container is set."""
    container = _MockContainer({"db_default": engine})
    ctx = BrimleyContext()
    ctx.container = container
    # Intentionally leave ctx.databases empty to prove container is used
    ctx.databases = {}

    func = SqlFunction(
        name="get_users",
        type="sql_function",
        return_shape="dict[]",
        sql_body="SELECT id, name FROM users",
    )
    result = _sql_runner.run(func, {}, ctx)
    assert len(result) == 2
    names = {r["name"] for r in result}
    assert names == {"Alice", "Bob"}


def test_sql_runner_falls_back_to_databases_when_no_container(engine):
    """SqlRunner falls back to context.databases when context.container is None."""
    ctx = BrimleyContext()
    ctx.container = None
    ctx.databases = {"default": engine}

    func = SqlFunction(
        name="get_users",
        type="sql_function",
        return_shape="dict[]",
        sql_body="SELECT id, name FROM users",
    )
    result = SqlRunner().run(func, {}, ctx)
    assert len(result) == 2


def test_sql_runner_container_provider_not_found_falls_back_to_databases(engine):
    """If container does not have the db_<name> provider, fall back to databases."""
    container = _MockContainer({})  # db_default not registered
    ctx = BrimleyContext()
    ctx.container = container
    ctx.databases = {"default": engine}

    func = SqlFunction(
        name="get_users",
        type="sql_function",
        return_shape="dict[]",
        sql_body="SELECT id, name FROM users",
    )
    result = SqlRunner().run(func, {}, ctx)
    assert len(result) == 2
