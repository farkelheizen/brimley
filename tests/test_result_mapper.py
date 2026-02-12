import pytest
from typing import Optional
from pydantic import Field
from brimley.core.context import BrimleyContext
from brimley.core.entity import Entity
from brimley.core.models import BrimleyFunction
from brimley.execution.result_mapper import ResultMapper

class MockUser(Entity):
    id: int
    username: str
    email: Optional[str] = None

@pytest.fixture
def context():
    ctx = BrimleyContext()
    MockUser.name = "MockUser"
    MockUser.model_rebuild()
    ctx.entities.register(MockUser) # type: ignore
    return ctx

def test_map_void_returns_none(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="void")
    assert ResultMapper.map_result([], func, context) is None
    assert ResultMapper.map_result({"any": "thing"}, func, context) is None

def test_map_primitive_string(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="string")
    assert ResultMapper.map_result("hello", func, context) == "hello"
    assert ResultMapper.map_result(123, func, context) == "123"

def test_map_primitive_int(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="int")
    assert ResultMapper.map_result(123, func, context) == 123
    assert ResultMapper.map_result("456", func, context) == 456

def test_map_entity_single(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="MockUser")
    raw = {"id": 1, "username": "alice", "email": "alice@example.com"}
    result = ResultMapper.map_result([raw], func, context)
    assert isinstance(result, MockUser)
    assert result.id == 1
    assert result.username == "alice"

def test_map_entity_single_from_dict(context):
    # Some runners might return a single dict instead of a list of one row
    func = BrimleyFunction(name="test", type="sql_function", return_shape="MockUser")
    raw = {"id": 1, "username": "alice"}
    result = ResultMapper.map_result(raw, func, context)
    assert isinstance(result, MockUser)
    assert result.id == 1

def test_map_entity_list(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="MockUser[]")
    raw = [
        {"id": 1, "username": "alice"},
        {"id": 2, "username": "bob"}
    ]
    result = ResultMapper.map_result(raw, func, context)
    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], MockUser)
    assert result[0].username == "alice"
    assert result[1].username == "bob"

def test_map_primitive_list(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="string[]")
    raw = ["a", "b", "c"]
    result = ResultMapper.map_result(raw, func, context)
    assert result == ["a", "b", "c"]

def test_map_structured_inline_shorthand(context):
    func = BrimleyFunction(
        name="test", 
        type="sql_function", 
        return_shape={
            "inline": {
                "count": "int",
                "status": "string"
            }
        }
    )
    raw = {"count": 10, "status": "active"}
    # Structured inline currently returns a dict or a synthesized model?
    # Design doc says "Validates and converts... into instances of that Entity" 
    # but for inline it might just be a validated dict or a dynamic Pydantic model.
    # Let's assume a validated dict for now or a DynamicModel.
    result = ResultMapper.map_result(raw, func, context)
    assert result == {"count": 10, "status": "active"}

def test_map_structured_entity_ref(context):
    func = BrimleyFunction(
        name="test",
        type="sql_function",
        return_shape={"entity_ref": "MockUser"}
    )
    raw = {"id": 1, "username": "alice"}
    result = ResultMapper.map_result(raw, func, context)
    assert isinstance(result, MockUser)

def test_map_strict_single_fails_on_multiple_rows(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="MockUser")
    raw = [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}]
    with pytest.raises(ValueError, match="Expected single row"):
        ResultMapper.map_result(raw, func, context)

def test_map_missing_fields_raises_validation_error(context):
    func = BrimleyFunction(name="test", type="sql_function", return_shape="MockUser")
    raw = {"id": 1} # Missing 'username'
    with pytest.raises(Exception): # Pydantic ValidationError
        ResultMapper.map_result(raw, func, context)
