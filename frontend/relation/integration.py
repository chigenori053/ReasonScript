"""Language-to-runtime integration for the `relation.*` namespace.

Phase 8 ("Tensor Logic hybrid") of the modernization plan calls for a
"relation tuple/join/projection/filter planner". This module implements
the *selection* (filter) half of relational algebra plus a few practical
utilities (`count`, `distinct_by`, `sort_by`) over `Array<Struct>` --
ReasonScript's existing "array of same-shaped structs" is exactly a
relation's tuple set, so no new data type is introduced.

`join` and `project` (projection) are deliberately NOT implemented here:
both change the row's field shape, hitting the same static-typing gap
`frontend/tensor/optimizers.py` documents for `optimizer.*` (the type
checker only resolves `.field` access on a `NamedTypeNode` backed by a
real `StructDeclarationNode` -- there is no way to synthesize one for a
join's or projection's derived field set). Unlike Optimizer, there is no
"return a single Tensor instead" escape hatch here: a join's output
*is* a set of rows with a new shape. Making that statically
type-checkable needs one of:

  1. Requiring the call site to already have a struct declared whose
     fields structurally match the derived output, found by searching
     the module's symbol table (duck typing against declared structs).
  2. New call-site syntax that names the target struct type explicitly.

Both are real language-design decisions this pass does not make. `filter_*`/
`distinct_by`/`sort_by` sidestep the problem entirely: they only ever
select a subset of *rows*, never change a row's *shape*, so the result
type is always identical to the input's `Array<Struct>` type -- no
synthetic type needed.

Every filter/sort function takes a `field` argument that must be a
string literal (ReasonScript has no closures/lambdas -- there is no way
to pass an arbitrary predicate, so field name + comparison value is the
only expressible criterion, mirroring how `tensor.softmax(input, axis)`
already takes an axis as a plain literal rather than a function).
"""

from __future__ import annotations

from typing import Any

from frontend.language_surface.nodes import CallExpressionNode, ExpressionNode, IdentifierNode, MemberAccessNode
from frontend.tensor.integration import _UNKNOWN, _literal

# name -> exact argument count.
RELATION_SIGNATURES: dict[str, int] = {
    "relation.filter_eq": 3,  # rows, field, value
    "relation.filter_ne": 3,
    "relation.filter_gt": 3,
    "relation.filter_gte": 3,
    "relation.filter_lt": 3,
    "relation.filter_lte": 3,
    "relation.count": 1,  # rows
    "relation.distinct_by": 2,  # rows, field
    "relation.sort_by": 3,  # rows, field, descending
}

# Argument positions (0-indexed) that must be a string literal field name.
_FIELD_ARGUMENT_POSITIONS: dict[str, int] = {
    "relation.filter_eq": 1,
    "relation.filter_ne": 1,
    "relation.filter_gt": 1,
    "relation.filter_gte": 1,
    "relation.filter_lt": 1,
    "relation.filter_lte": 1,
    "relation.distinct_by": 1,
    "relation.sort_by": 1,
}


class RelationSemanticError(ValueError):
    """Stable semantic diagnostic raised before Reason IR lowering."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


def relation_call_name(value: Any) -> str | None:
    """Resolve ``relation.name(...)`` without treating ``relation`` as a module."""
    value = value.expression if isinstance(value, ExpressionNode) else value
    if not isinstance(value, CallExpressionNode):
        return None
    callee = value.callee
    if (
        isinstance(callee, MemberAccessNode)
        and isinstance(callee.object, IdentifierNode)
        and callee.object.name == "relation"
    ):
        return f"relation.{callee.member}"
    return None


def validate_relation_call(value: CallExpressionNode) -> None:
    name = relation_call_name(value)
    if name is None:
        return
    if name not in RELATION_SIGNATURES:
        raise RelationSemanticError("REL-001", f"unknown Relation function: {name}")
    expected = RELATION_SIGNATURES[name]
    if len(value.arguments) != expected:
        raise RelationSemanticError(
            "REL-002",
            f"Relation function argument count mismatch: {name} expects {expected}",
        )
    field_position = _FIELD_ARGUMENT_POSITIONS.get(name)
    if field_position is not None:
        literal = _literal(value.arguments[field_position])
        if literal is _UNKNOWN or not isinstance(literal, str):
            raise RelationSemanticError(
                "REL-003", f"Relation field name must be a string literal: {name}"
            )
