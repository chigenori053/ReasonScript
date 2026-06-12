"""Immutable Python DTO binding for reasonscript-ast/0.1."""

from frontend.ast import (
    AST_VERSION,
    ConstraintNode,
    ContextNode,
    GoalNode,
    MetadataNode,
    ModuleNode,
    StateNode,
    TransitionNode,
    from_json_value,
    to_json_value,
)


def from_dict(value):
    return from_json_value(value)


def to_dict(value):
    return to_json_value(value)


__all__ = [
    "AST_VERSION",
    "ConstraintNode",
    "ContextNode",
    "GoalNode",
    "MetadataNode",
    "ModuleNode",
    "StateNode",
    "TransitionNode",
    "from_dict",
    "to_dict",
]
