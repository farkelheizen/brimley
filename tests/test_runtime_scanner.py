import types
from typing import Annotated

from brimley import AppState, Config, entity, function
from brimley.core.models import DiscoveredEntity, PythonFunction, SqlFunction, TemplateFunction
from brimley.discovery.runtime import scan_module


def test_scan_module_discovers_python_function_with_inferred_metadata():
    module = types.ModuleType("runtime_scan_mod")

    @function(name="greet", mcpType="tool", reload=False)
    def greet(name: str) -> str:
        return f"Hello {name}"

    greet.__module__ = module.__name__
    module.greet = greet

    discovered = scan_module(module)

    assert len(discovered) == 1
    item = discovered[0]
    assert isinstance(item, PythonFunction)
    assert item.name == "greet"
    assert item.handler == "runtime_scan_mod.greet"
    assert item.reload is False
    assert item.return_shape == "string"
    assert item.mcp is not None
    assert item.mcp.type == "tool"
    assert item.arguments == {"inline": {"name": "string"}}


def test_scan_module_discovers_python_function_annotated_context_args():
    module = types.ModuleType("runtime_scan_context_mod")

    @function
    def greet(
        prompt: str,
        session_id: Annotated[str, AppState("session_id")],
        app_name: Annotated[str, Config("app_name")],
    ) -> str:
        return prompt

    greet.__module__ = module.__name__
    module.greet = greet

    discovered = scan_module(module)

    assert len(discovered) == 1
    item = discovered[0]
    assert isinstance(item, PythonFunction)
    assert item.arguments is not None
    inline = item.arguments["inline"]
    assert inline["prompt"] == "string"
    assert inline["session_id"]["from_context"] == "app.session_id"
    assert inline["app_name"]["from_context"] == "config.app_name"


def test_scan_module_discovers_sql_and_template_functions_from_metadata_type():
    module = types.ModuleType("runtime_scan_assets_mod")

    @function(type="sql_function", content="SELECT * FROM users", return_shape="list[dict]", connection="analytics")
    def get_users() -> str:
        return "unused"

    @function(type="template_function", content="Hello {{ args.name }}", return_shape="string")
    def greet_template() -> str:
        return "unused"

    get_users.__module__ = module.__name__
    greet_template.__module__ = module.__name__
    module.get_users = get_users
    module.greet_template = greet_template

    discovered = scan_module(module)

    assert len(discovered) == 2
    sql_items = [item for item in discovered if isinstance(item, SqlFunction)]
    template_items = [item for item in discovered if isinstance(item, TemplateFunction)]

    assert len(sql_items) == 1
    assert len(template_items) == 1

    assert sql_items[0].name == "get_users"
    assert sql_items[0].sql_body == "SELECT * FROM users"
    assert sql_items[0].connection == "analytics"
    assert sql_items[0].return_shape == "list[dict]"

    assert template_items[0].name == "greet_template"
    assert template_items[0].template_body == "Hello {{ args.name }}"
    assert template_items[0].return_shape == "string"


def test_scan_module_discovers_entity_classes_from_decorator_metadata():
    module = types.ModuleType("runtime_scan_entity_mod")

    @entity(name="User")
    class UserRecord:
        pass

    UserRecord.__module__ = module.__name__
    module.UserRecord = UserRecord

    discovered = scan_module(module)

    assert len(discovered) == 1
    item = discovered[0]
    assert isinstance(item, DiscoveredEntity)
    assert item.name == "User"
    assert item.type == "python_entity"
    assert item.handler == "runtime_scan_entity_mod.UserRecord"
