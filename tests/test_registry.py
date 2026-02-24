import pytest
from brimley.core.registry import Registry
from brimley.core.models import BrimleyFunction

class MockFunction(BrimleyFunction):
    name: str
    type: str = "mock"
    return_shape: str = "void"

def test_registry_registration():
    reg = Registry()
    f = MockFunction(name="test_func")
    reg.register(f)
    
    assert reg.get("test_func") == f
    assert "test_func" in reg

def test_registry_get_missing():
    reg = Registry()
    with pytest.raises(KeyError):
        reg.get("missing")

def test_registry_duplicate_error():
    """Registry should enforce uniqueness even if Scanner checks it too."""
    reg = Registry()
    f = MockFunction(name="dup")
    reg.register(f)
    
    with pytest.raises(ValueError, match="already registered"):
        reg.register(f)

def test_registry_len_iteration():
    reg = Registry()
    reg.register(MockFunction(name="a"))
    reg.register(MockFunction(name="b"))
    
    assert len(reg) == 2
    names = {f.name for f in reg}
    assert names == {"a", "b"}


def test_registry_alias_resolution_maps_to_canonical_target():
    reg = Registry()
    item = MockFunction(name="canonical")
    reg.register(item)

    reg.register_alias(alias="legacy_name", target="canonical")

    assert reg.get("legacy_name") is item


def test_registry_alias_cannot_shadow_existing_canonical_name():
    reg = Registry()
    reg.register(MockFunction(name="a"))
    reg.register(MockFunction(name="b"))

    with pytest.raises(ValueError, match="cannot shadow"):
        reg.register_alias(alias="a", target="b")


def test_registry_alias_chain_is_rejected():
    reg = Registry()
    reg.register(MockFunction(name="canonical"))
    reg.register_alias(alias="legacy", target="canonical")

    with pytest.raises(ValueError, match="Alias chains are not supported"):
        reg.register_alias(alias="older", target="legacy")
