import importlib
import inspect
import asyncio
import sys
from contextlib import contextmanager
from pathlib import Path
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
        try:
            handler = self._load_handler(func.handler, context=context, runtime_injections=runtime_injections)
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            handler = self._load_handler(func.handler)
        
        # Prepare arguments
        final_args = self._resolve_dependencies(handler, args, context, runtime_injections=runtime_injections)
        
        raw_result = handler(**final_args)

        if inspect.isawaitable(raw_result):
            async def _await_and_map() -> Any:
                awaited_result = await raw_result
                return ResultMapper.map_result(awaited_result, func, context)

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(_await_and_map())

            return _await_and_map()
        
        # Validate result against return_shape if specified
        return ResultMapper.map_result(raw_result, func, context)

    def _load_handler(
        self,
        handler_path: str,
        context: Optional[BrimleyContext] = None,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ):
        """
        Loads the function from the dot-notation path string.
        e.g. "my_module.utils.my_func"
        """
        if not handler_path:
            raise ValueError("PythonFunction requires a valid 'handler' path.")

        try:
            module_name, func_name = handler_path.rsplit(".", 1)
            module = self._import_module_with_roots(module_name, context=context, runtime_injections=runtime_injections)
            func = getattr(module, func_name)
            if not callable(func):
                raise TypeError(f"Handler '{handler_path}' is not callable.")
            return func
        except (ValueError, ImportError, AttributeError) as e:
            raise ImportError(f"Could not load handler '{handler_path}': {str(e)}")

    def _import_module_with_roots(
        self,
        module_name: str,
        context: Optional[BrimleyContext] = None,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ):
        """Import module, retrying with candidate root directories on sys.path."""
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as first_error:
            roots = self._collect_import_roots(context=context, runtime_injections=runtime_injections)
            if not roots:
                raise first_error

            with self._temporary_sys_path(roots):
                try:
                    return importlib.import_module(module_name)
                except ModuleNotFoundError:
                    discovered_roots = self._discover_module_roots(module_name, roots)
                    if not discovered_roots:
                        raise first_error

            with self._temporary_sys_path(discovered_roots):
                return importlib.import_module(module_name)

    def _collect_import_roots(
        self,
        context: Optional[BrimleyContext] = None,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        """Collect candidate filesystem roots for Python module imports."""
        candidate_values: list[Any] = []

        if runtime_injections:
            candidate_values.extend(
                runtime_injections.get(key)
                for key in ("root_dir", "project_root", "root", "scan_root")
            )

        if context is not None and isinstance(context.app, dict):
            candidate_values.extend(
                context.app.get(key)
                for key in ("root_dir", "project_root", "root", "scan_root")
            )

        roots: list[str] = []
        for value in candidate_values:
            if value is None:
                continue

            root_path = Path(value).expanduser().resolve()
            root_path_str = str(root_path)
            if root_path.exists() and root_path_str not in roots:
                roots.append(root_path_str)

        return roots

    def _discover_module_roots(self, module_name: str, roots: list[str]) -> list[str]:
        """Discover additional import roots by locating module files under known roots."""
        discovered: list[str] = []
        module_path = Path(*module_name.split("."))
        terminal_name = module_path.name

        for root in roots:
            root_path = Path(root)
            if not root_path.exists():
                continue

            exact_module_file = root_path / module_path.with_suffix(".py")
            exact_package_init = root_path / module_path / "__init__.py"
            if exact_module_file.exists() or exact_package_init.exists():
                if root not in discovered:
                    discovered.append(root)
                continue

            for match in root_path.rglob(f"{terminal_name}.py"):
                match_parent = str(match.parent.resolve())
                if match_parent not in discovered:
                    discovered.append(match_parent)

        return discovered

    @contextmanager
    def _temporary_sys_path(self, roots: list[str]):
        """Temporarily prepend import roots to sys.path."""
        inserted: list[str] = []
        for root in reversed(roots):
            if root not in sys.path:
                sys.path.insert(0, root)
                inserted.append(root)

        try:
            yield
        finally:
            for root in inserted:
                try:
                    sys.path.remove(root)
                except ValueError:
                    continue

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
            return normalized in {
                "Context",
                "mcp.server.fastmcp.Context",
                "fastmcp.Context",
                "fastmcp.server.context.Context",
            }

        annotation_name = getattr(annotation, "__name__", None)
        annotation_module = getattr(annotation, "__module__", None)
        return annotation_name == "Context" and annotation_module in {
            "mcp.server.fastmcp",
            "fastmcp.server.context",
        }
