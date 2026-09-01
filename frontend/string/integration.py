"""Language-to-runtime integration for the `string.*` namespace.

Phase 2 of the recommended fix plan ("String／Collection標準ライブラリ"):
extending `+` to strings would make the existing numeric-only arithmetic
type rule (`TYPE-V004`) ambiguous, so string concatenation and the other
minimal string operations get an explicit namespace instead, mirroring
how `relation.*`/`tensor.*`/`optimizer.*` already work.

Minimal set: `string.concat(a, b)`, `string.join(separator, values)`,
`string.length(value)`, `string.from_int(value)`, `string.from_float(value)`,
`string.slice(value, start, end)`. Every argument is an ordinary
expression (unlike `relation.*`'s field-name arguments, nothing here
needs to be a compile-time string literal).
"""

from __future__ import annotations

from typing import Any

from frontend.language_surface.nodes import CallExpressionNode, ExpressionNode, IdentifierNode, MemberAccessNode

# name -> exact argument count.
STRING_SIGNATURES: dict[str, int] = {
    "string.concat": 2,  # a, b
    "string.join": 2,  # separator, values
    "string.length": 1,  # value
    "string.from_int": 1,  # value
    "string.from_float": 1,  # value
    "string.slice": 3,  # value, start, end
}


class StringSemanticError(ValueError):
    """Stable semantic diagnostic raised before Reason IR lowering."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


def string_call_name(value: Any) -> str | None:
    """Resolve ``string.name(...)`` without treating ``string`` as a module."""
    value = value.expression if isinstance(value, ExpressionNode) else value
    if not isinstance(value, CallExpressionNode):
        return None
    callee = value.callee
    if (
        isinstance(callee, MemberAccessNode)
        and isinstance(callee.object, IdentifierNode)
        and callee.object.name == "string"
    ):
        return f"string.{callee.member}"
    return None


def validate_string_call(value: CallExpressionNode) -> None:
    name = string_call_name(value)
    if name is None:
        return
    if name not in STRING_SIGNATURES:
        raise StringSemanticError("STR-001", f"unknown String function: {name}")
    expected = STRING_SIGNATURES[name]
    if len(value.arguments) != expected:
        raise StringSemanticError(
            "STR-002",
            f"String function argument count mismatch: {name} expects {expected}",
        )
