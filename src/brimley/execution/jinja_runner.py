from typing import Any, Dict
from jinja2 import Environment, BaseLoader

from brimley.core.models import TemplateFunction
from brimley.core.context import BrimleyContext

class JinjaRunner:
    """
    Executes TemplateFunctions using Jinja2.
    """
    def __init__(self):
        # We use a base loader since we render strings directly
        self.env = Environment(loader=BaseLoader())

    def run(self, func: TemplateFunction, resolved_args: Dict[str, Any], context: BrimleyContext) -> str:
        """
        Renders the template body with the provided arguments and context.
        """
        if not func.template_body:
            return ""

        template = self.env.from_string(func.template_body)
        
        # We inject:
        # 1. 'args': The resolved arguments dict
        # 2. 'context': The BrimleyContext object
        render_context = {
            "args": resolved_args,
            "context": context
        }
        
        return template.render(**render_context)
