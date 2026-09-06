"""ReasonScript Console and standard output integration."""

from frontend.console.integration import (
    CONSOLE_METHODS,
    ConsoleSemanticError,
    console_call_name,
    is_unsupported_js_call,
    validate_console_call,
)

__all__ = [
    "CONSOLE_METHODS",
    "ConsoleSemanticError",
    "console_call_name",
    "is_unsupported_js_call",
    "validate_console_call",
]
