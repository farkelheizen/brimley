from typing import Any, Dict, Optional
from brimley.core.models import BrimleyFunction, PythonFunction, SqlFunction, TemplateFunction
from brimley.core.context import BrimleyContext
from brimley.execution.python_runner import PythonRunner
from brimley.execution.sql_runner import SqlRunner
from brimley.execution.jinja_runner import JinjaRunner

class Dispatcher:
    """
    Routes execution to the appropriate runner based on function type.
    """
    def __init__(self):
        self.python_runner = PythonRunner()
        self.sql_runner = SqlRunner()
        self.jinja_runner = JinjaRunner()

    def run(
        self,
        func: BrimleyFunction,
        args: Dict[str, Any],
        context: BrimleyContext,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # Note: We match against specific types. 
        # If new types are added, this needs updating.
        
        if func.type == "python_function": 
            # Check type string or isinstance if classes are distinct
            if isinstance(func, PythonFunction):
                return self.python_runner.run(func, args, context, runtime_injections=runtime_injections)
            
        elif func.type == "sql_function":
            if isinstance(func, SqlFunction):
                return self.sql_runner.run(func, args, context)
            
        elif func.type == "template_function":
             if isinstance(func, TemplateFunction):
                return self.jinja_runner.run(func, args, context)
                
        raise NotImplementedError(f"No runner for function type: {func.type} ({type(func)})")
