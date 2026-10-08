import inspect
from typing import Callable, Any, Dict, Optional, get_type_hints


def _python_type_to_json_type(t) -> str:
    if t is int:
        return "integer"
    if t is float:
        return "number"
    if t is bool:
        return "boolean"
    if t is list:
        return "array"
    if t is dict:
        return "object"
    return "string"


class ToolWrapper:
    def __init__(self, fn: Callable, name: Optional[str] = None, description: Optional[str] = None):
        self.fn = fn
        self.name = name or fn.__name__
        self.description = (description or fn.__doc__ or "").strip()
        self.__name__ = self.name
        self.__doc__ = self.description

        # Build JSON Schema for function parameters
        sig = inspect.signature(fn)
        type_hints = {}
        try:
            type_hints = get_type_hints(fn)
        except Exception:
            type_hints = getattr(fn, "__annotations__", {})

        properties: Dict[str, Any] = {}
        required = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = type_hints.get(param_name, str)
            # Handle typing.Optional
            origin = getattr(param_type, "__origin__", None)
            if origin is not None:
                args = getattr(param_type, "__args__", ())
                if len(args) > 0 and args[0] is not type(None):
                    param_type = args[0]

            properties[param_name] = {
                "type": _python_type_to_json_type(param_type),
                "description": f"Parameter '{param_name}' for {self.name}",
            }
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        self.parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        self.openai_tool = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    def invoke(self, input_data: Any) -> Any:
        if isinstance(input_data, dict):
            return self.fn(**input_data)
        elif isinstance(input_data, (tuple, list)):
            return self.fn(*input_data)
        elif input_data is not None:
            return self.fn(input_data)
        return self.fn()


def tool(name_or_fn=None, *args, **kwargs):
    if callable(name_or_fn):
        return ToolWrapper(name_or_fn)

    def decorator(fn):
        return ToolWrapper(fn, name=name_or_fn)

    return decorator
