"""ReasonScript Tensor Standard Functions v0.1 public API.

Resolve reference-runtime exports on demand so compiler imports stay backend neutral.
"""

from importlib import import_module as _import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .runtime import (
        TensorDiagnostic,
        TensorError,
        TensorFunctionContract,
        TensorPolicy,
        TensorRuntime,
        TensorValueRef,
        create_tensor_runtime,
        tensor_function_contracts,
    )


__all__ = [
    "TensorDiagnostic",
    "TensorError",
    "TensorFunctionContract",
    "TensorPolicy",
    "TensorRuntime",
    "TensorValueRef",
    "create_tensor_runtime",
    "tensor_function_contracts",
]


# A package reload must discard aliases cached from an older runtime module.
for _name in __all__:
    globals().pop(_name, None)
del _name


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_import_module(".runtime", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
