from typing import Any, Dict, Optional

from brimley.core.context import BrimleyContext
from brimley.execution.arguments import ArgumentResolver
from brimley.execution.dispatcher import Dispatcher


def execute_function_by_name(
    context: BrimleyContext,
    function_name: str,
    input_data: Dict[str, Any],
    runtime_injections: Optional[Dict[str, Any]] = None,
) -> Any:
    """Execute a registered Brimley function by name.

    This helper preserves the standard invocation pipeline used by CLI/REPL:
    function lookup, argument resolution, and dispatcher execution.
    """
    func = context.functions.get(function_name)
    resolved_args = ArgumentResolver.resolve(func, input_data, context)
    dispatcher = Dispatcher()
    return dispatcher.run(func, resolved_args, context, runtime_injections=runtime_injections)
