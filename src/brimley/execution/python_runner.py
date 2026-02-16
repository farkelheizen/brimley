import importlib
import inspect
from typing import Any, Dict, Optional, get_args, get_origin, Annotated
from brimley.core.models import PythonFunction
from brimley.core.context import BrimleyContext
from brimley.core.di import AppState, Config, Connection
from brimley.execution.result_mapper import ResultMapper

class PythonRunner:
    """
    Executes a PythonFunction with robust Dependency Injection.
    """

    def run(
        self,
        func: PythonFunction,
        args: Dict[str, Any],
        context: BrimleyContext,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Executes the function handler.
        1. Loads the callable.
        2. Inspects signature for DI markers.
        3. Merges explicit args with injected args.
        4. Calls the function.
        """
        handler = self._load_handler(func.handler)
        
        # Prepare arguments
        final_args = self._resolve_dependencies(handler, args, context, runtime_injections=runtime_injections)
        
        raw_result = handler(**final_args)
        
        # Validate result against return_shape if specified
        return ResultMapper.map_result(raw_result, func, context)

    def _load_handler(self, handler_path: str):
        """
        Loads the function from the dot-notation path string.
        e.g. "my_module.utils.my_func"
        """
        if not handler_path:
            raise ValueError("PythonFunction requires a valid 'handler' path.")

        try:
            module_name, func_name = handler_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            func = getattr(module, func_name)
            if not callable(func):
                raise TypeError(f"Handler '{handler_path}' is not callable.")
            return func
        except (ValueError, ImportError, AttributeError) as e:
            raise ImportError(f"Could not load handler '{handler_path}': {str(e)}")

    def _resolve_dependencies(
        self,
        handler,
        resolved_args: Dict[str, Any],
        context: BrimleyContext,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Inspects the handler signature and injects dependencies.
        """
        # We use inspect.signature to get parameter names and defaults
        sig = inspect.signature(handler)
        # We use get_type_hints to correctly resolve forward references and get Annotated objects
        type_hints = {}
        try:
            type_hints = inspect.get_annotations(handler, eval_str=True)
        except Exception:
             # Fallback if evaluation fails (e.g. missing imports in scope), 
             # though get_annotations usually handles this if globals/locals are correct.
             # For simpler cases, inspect.signature contains annotation objects too.
             pass

        final_kwargs = {}

        for param_name, param in sig.parameters.items():
            # If the user supplied it explicitly (via args), that takes precedence
            # EXCEPT for system internals which likely shouldn't be overridden by user?
            # Actually, typically DI overrides or conflicts. 
            # In Brimley logic, 'args' contains validated user/context inputs.
            # If 'args' has it, we use it. If not, we try DI.
            
            if param_name in resolved_args:
                final_kwargs[param_name] = resolved_args[param_name]
                continue
            
            # Check for Dependency Injection via Annotation
            annotation = type_hints.get(param_name, param.annotation)
            
            injected_value, is_injected = self._get_dependency(
                annotation,
                context,
                runtime_injections=runtime_injections,
            )
            
            if is_injected:
                final_kwargs[param_name] = injected_value
            elif param.default is not inspect.Parameter.empty:
                # Use default if no injection and no user input
                final_kwargs[param_name] = param.default
            else:
                # If required and missing, we let the call fail naturally (or raise better error)
                pass

        return final_kwargs

    def _get_dependency(
        self,
        annotation,
        context: BrimleyContext,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, bool]:
        """
        Parses an annotation to see if it requests a dependency.
        Returns (value, True) if injected, or (None, False) if not.
        Raises KeyError/AttributeError if dependency is found but missing in context.
        """
        if self._is_brimley_context_annotation(annotation):
            return context, True

        if self._is_fastmcp_context_annotation(annotation):
            if runtime_injections:
                for key in (
                    "mcp_context",
                    "mcp",
                    "ctx",
                    "context",
                    "fastmcp_context",
                    "mcp.server.fastmcp.Context",
                ):
                    if key in runtime_injections:
                        return runtime_injections[key], True

            return None, False

        if get_origin(annotation) is Annotated:
            args = get_args(annotation)
            # args[0] is the type, args[1:] are metadata
            
            for meta in args[1:]:
                # Check for AppState("key")
                if isinstance(meta, AppState):
                    # Strict: Raise KeyError if missing
                    return context.app[meta.key], True
                
                # Check for Config("key")
                if isinstance(meta, Config):
                    # Strict: Raise AttributeError if missing
                    val = getattr(context.config, meta.key)
                    return val, True

                # Check for Connection string
                if args[0] is Connection or (hasattr(args[0], "__name__") and args[0].__name__ == "Connection"):
                    if isinstance(meta, str):
                        # Strict: Raise KeyError if missing
                        return context.databases[meta], True
        
        return None, False

    def _is_brimley_context_annotation(self, annotation: Any) -> bool:
        """
        Determine whether an annotation targets BrimleyContext injection.
        """
        if annotation is BrimleyContext:
            return True

        if isinstance(annotation, type):
            try:
                return issubclass(annotation, BrimleyContext)
            except TypeError:
                return False

        if isinstance(annotation, str):
            normalized = annotation.replace(" ", "")
            return normalized in {"BrimleyContext", "brimley.core.context.BrimleyContext"}

        return False

    def _is_fastmcp_context_annotation(self, annotation: Any) -> bool:
        """
        Determine whether an annotation targets FastMCP Context injection.
        """
        if isinstance(annotation, str):
            normalized = annotation.replace(" ", "")
            return normalized in {"Context", "mcp.server.fastmcp.Context", "fastmcp.Context"}

        annotation_name = getattr(annotation, "__name__", None)
        annotation_module = getattr(annotation, "__module__", None)
        return annotation_name == "Context" and annotation_module == "mcp.server.fastmcp"
