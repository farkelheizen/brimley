from brimley.core.context import BrimleyContext

def test_context_init_with_config():
    config_data = {
        "brimley": {
            "app_name": "Test App",
            "env": "test"
        },
        "config": {
            "api_key": "123",
            "feature_x": True
        },
        "state": {
            "user": "admin"
        }
    }
    
    ctx = BrimleyContext(config_dict=config_data)
    
    assert ctx.settings.app_name == "Test App"
    assert ctx.settings.env == "test"
    assert ctx.config.api_key == "123" # Pydantic extra='allow'
    assert getattr(ctx.config, "feature_x") is True
    assert ctx.app["user"] == "admin"

def test_context_default_init():
    ctx = BrimleyContext()
    assert ctx.settings.app_name == "Brimley App"
    assert ctx.app == {}
