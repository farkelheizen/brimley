from brimley.schemas import ReturnType

def test_return_type_list():
    """Ensure LIST is a valid ReturnType."""
    assert ReturnType.LIST == "LIST"
