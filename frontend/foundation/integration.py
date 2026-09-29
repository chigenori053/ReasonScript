"""Language-to-runtime integration for the foundation namespaces.

- ``math.*``: scalar math over Int/Float values, independent of Tensors.
- ``sequence.range(start, end, step)``: bounded numeric sequences.
- ``serialize.json(value)``: canonical in-language JSON serialization.
- ``artifact.write_text(path, content[, overwrite])``: permission-aware
  UTF-8 output below the runtime resource root.

This module owns the static contract (names, arity, argument and result
types). The semantics execute only in the native Rust runtime
(``ReasonRuntime/crates/computation-ir/src/foundation_dispatch.rs``); the
IR lowers every call to a single ``call_foundation`` node.
"""

from __future__ import annotations

from typing import Any

from frontend.language_surface.nodes import (
    ArrayTypeNode,
    CallExpressionNode,
    ExpressionNode,
    FloatLiteralNode,
    IdentifierNode,
    IntegerLiteralNode,
    MemberAccessNode,
    NamedTypeNode,
    ParenthesizedExpressionNode,
    PrimitiveKind,
    PrimitiveTypeNode,
    UnaryExpressionNode,
    UnaryOperator,
)

FOUNDATION_NAMESPACES = frozenset({"math", "sequence", "serialize", "artifact"})

# name -> (minimum, maximum) argument count.
FOUNDATION_SIGNATURES: dict[str, tuple[int, int]] = {
    "math.abs": (1, 1),
    "math.min": (2, 2),
    "math.max": (2, 2),
    "math.floor": (1, 1),
    "math.ceil": (1, 1),
    "math.round": (1, 1),
    "math.sqrt": (1, 1),
    "math.sin": (1, 1),
    "math.cos": (1, 1),
    "math.tan": (1, 1),
    "math.log": (1, 1),
    "math.exp": (1, 1),
    "math.approx_equal": (3, 3),
    "sequence.range": (3, 3),
    "serialize.json": (1, 1),
    "artifact.write_text": (2, 3),
}

_FAMILY = {"math": "MATH", "sequence": "SEQ", "serialize": "SER", "artifact": "ART"}

ARTIFACT_RESULT_TYPE = "ArtifactResult"
ARTIFACT_RESULT_FIELDS = {
    "path": PrimitiveTypeNode(PrimitiveKind.STRING),
    "bytes_written": PrimitiveTypeNode(PrimitiveKind.INT),
}

# Runtime handles with no data representation.
UNSERIALIZABLE_TYPES = frozenset({
    "Tensor",
    "TensorArtifactReceipt",
    "VisionObservation",
    "VisionBuildResult",
    "ReasonObject",
    "ReasonObjectSnapshot",
    "ReasonTransaction",
})

_INT = PrimitiveTypeNode(PrimitiveKind.INT)
_FLOAT = PrimitiveTypeNode(PrimitiveKind.FLOAT)
_BOOL = PrimitiveTypeNode(PrimitiveKind.BOOL)
_STRING = PrimitiveTypeNode(PrimitiveKind.STRING)
_NUMERIC = frozenset({_INT, _FLOAT})


class FoundationSemanticError(ValueError):
    """Stable semantic diagnostic raised before Reason IR lowering."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


def foundation_call_name(value: Any) -> str | None:
    """Resolve ``math.name(...)``-style calls on a foundation namespace."""
    value = value.expression if isinstance(value, ExpressionNode) else value
    if not isinstance(value, CallExpressionNode):
        return None
    callee = value.callee
    if (
        isinstance(callee, MemberAccessNode)
        and isinstance(callee.object, IdentifierNode)
        and callee.object.name in FOUNDATION_NAMESPACES
    ):
        return f"{callee.object.name}.{callee.member}"
    return None


def _family(name: str) -> str:
    return _FAMILY[name.split(".", 1)[0]]


def validate_foundation_call(value: CallExpressionNode) -> str:
    name = foundation_call_name(value)
    if name is None:
        raise FoundationSemanticError("FND-001", "not a foundation call")
    family = _family(name)
    if name not in FOUNDATION_SIGNATURES:
        raise FoundationSemanticError(f"{family}-001", f"unknown foundation function: {name}")
    minimum, maximum = FOUNDATION_SIGNATURES[name]
    if not minimum <= len(value.arguments) <= maximum:
        expected = str(minimum) if minimum == maximum else f"{minimum} to {maximum}"
        raise FoundationSemanticError(
            f"{family}-002", f"{name} expects {expected} arguments, got {len(value.arguments)}"
        )
    if name == "sequence.range" and _literal_number(value.arguments[2]) == 0:
        raise FoundationSemanticError("SEQ-004", "sequence.range step must not be zero")
    return name


def _literal_number(value: Any) -> int | float | None:
    value = value.expression if isinstance(value, ExpressionNode) else value
    if isinstance(value, ParenthesizedExpressionNode):
        return _literal_number(value.expression)
    if isinstance(value, (IntegerLiteralNode, FloatLiteralNode)):
        return value.value
    if isinstance(value, UnaryExpressionNode) and value.operator == UnaryOperator.NEGATE:
        inner = _literal_number(value.operand)
        return None if inner is None else -inner
    return None


def foundation_call_type(name: str, argument_types: list[Any], unknown: Any) -> Any:
    """Static result type; raises for statically invalid argument types."""
    family = _family(name)

    def require(index: int, allowed: frozenset[Any], description: str) -> None:
        actual = argument_types[index]
        # Compare with == rather than hashing: some checker types are unhashable.
        if actual is not unknown and not any(actual == item for item in allowed):
            raise FoundationSemanticError(
                f"{family}-003", f"{name} argument {index + 1} must be {description}"
            )

    if name.startswith("math."):
        for index in range(len(argument_types)):
            require(index, _NUMERIC, "Int or Float")
        if name == "math.approx_equal":
            return _BOOL
        if name in {"math.abs", "math.floor", "math.ceil", "math.round"}:
            return argument_types[0]
        if name in {"math.min", "math.max"}:
            if unknown in argument_types:
                return _FLOAT if _FLOAT in argument_types else unknown
            return _INT if argument_types == [_INT, _INT] else _FLOAT
        return _FLOAT
    if name == "sequence.range":
        for index in range(3):
            require(index, _NUMERIC, "Int or Float")
        if _FLOAT in argument_types:
            return ArrayTypeNode(_FLOAT)
        if unknown in argument_types:
            return ArrayTypeNode(unknown)
        return ArrayTypeNode(_INT)
    if name == "serialize.json":
        actual = argument_types[0]
        if isinstance(actual, NamedTypeNode) and actual.name in UNSERIALIZABLE_TYPES:
            raise FoundationSemanticError(
                "SER-003", f"serialize.json does not support {actual.name} values"
            )
        return _STRING
    if name == "artifact.write_text":
        require(0, frozenset({_STRING}), "String")
        require(1, frozenset({_STRING}), "String")
        if len(argument_types) == 3:
            require(2, frozenset({_BOOL}), "Bool")
        return NamedTypeNode(ARTIFACT_RESULT_TYPE)
    raise FoundationSemanticError(f"{family}-001", f"unknown foundation function: {name}")
