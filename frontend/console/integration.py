"""Language-to-runtime integration for the `Console.*` and `print` APIs.

RS-DXLI-07: ReasonScript native standard output APIs.
- Canonical API: `Console.log/info/warn/error`
- Convenience API: `print`
- Unsupported JavaScript APIs (e.g. `Js.log`) reject with `NAM-2004`.
"""

from __future__ import annotations

from typing import Any

from frontend.language_surface.nodes import (
    CallExpressionNode,
    ExpressionNode,
    IdentifierNode,
    MemberAccessNode,
    RuntimeCallExpressionNode,
    RuntimeCallKind,
)

CONSOLE_METHODS = {"log", "info", "warn", "error"}


class ConsoleSemanticError(ValueError):
    """Stable semantic diagnostic raised before Reason IR lowering."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


def console_call_name(value: Any) -> str | None:
    """Resolve Console.log/info/warn/error or print(...) call name."""
    value = value.expression if isinstance(value, ExpressionNode) else value
    if isinstance(value, RuntimeCallExpressionNode) and value.kind == RuntimeCallKind.PRINT:
        return "print"
    if not isinstance(value, CallExpressionNode):
        return None
    callee = value.callee
    if isinstance(callee, IdentifierNode) and callee.name == "print":
        return "print"
    if (
        isinstance(callee, MemberAccessNode)
        and isinstance(callee.object, IdentifierNode)
        and callee.object.name == "Console"
    ):
        return f"Console.{callee.member}"
    return None


def is_unsupported_js_call(value: Any) -> bool:
    """Detect if expression is an unsupported JavaScript API call (e.g. Js.log)."""
    value = value.expression if isinstance(value, ExpressionNode) else value
    if isinstance(value, CallExpressionNode):
        callee = value.callee
        if (
            isinstance(callee, MemberAccessNode)
            and isinstance(callee.object, IdentifierNode)
            and callee.object.name == "Js"
        ):
            return True
    elif isinstance(value, MemberAccessNode):
        if isinstance(value.object, IdentifierNode) and value.object.name == "Js":
            return True
    return False


def validate_console_call(value: CallExpressionNode) -> None:
    name = console_call_name(value)
    if name is None:
        return
    if name != "print":
        member = name.split(".", 1)[1]
        if member not in CONSOLE_METHODS:
            raise ConsoleSemanticError("CON-001", f"unknown Console function: {name}")
    if len(value.arguments) < 1:
        raise ConsoleSemanticError("CON-002", f"{name}() expects at least one argument")
