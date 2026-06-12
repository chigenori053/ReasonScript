"""Semantic validation for the ReasonScript AST."""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

from .nodes import (
    AST_VERSION,
    ConstraintNode,
    ContextNode,
    GoalNode,
    MetadataNode,
    ModuleNode,
    StateNode,
    TransitionNode,
)


class AstValidationError(ValueError):
    """Raised when an AST cannot be lowered to Reason IR."""


def validate(module: ModuleNode) -> None:
    if not isinstance(module, ModuleNode):
        raise AstValidationError("AST root must be ModuleNode")
    if module.version != AST_VERSION:
        raise AstValidationError(f"unsupported AST version: {module.version}")
    if not module.declarations:
        raise AstValidationError("ModuleNode.declarations must not be empty")

    nodes = (module, *module.declarations, *module.metadata)
    _validate_unique_node_ids(nodes)
    _validate_imports(module.imports)

    goals = [node for node in module.declarations if isinstance(node, GoalNode)]
    states = [node for node in module.declarations if isinstance(node, StateNode)]
    if len(goals) != 1:
        raise AstValidationError("ModuleNode must contain exactly one GoalNode")
    if len(states) != 1:
        raise AstValidationError("ModuleNode must contain exactly one initial StateNode")

    semantic_ids: dict[type[Any], set[str]] = {
        TransitionNode: set(),
        ConstraintNode: set(),
        ContextNode: set(),
    }
    metadata_keys: set[str] = set()
    for node in module.declarations:
        _validate_declaration(node)
        field_name = {
            TransitionNode: "transition_id",
            ConstraintNode: "constraint_id",
            ContextNode: "context_id",
        }.get(type(node))
        if field_name:
            identifier = getattr(node, field_name)
            if identifier in semantic_ids[type(node)]:
                raise AstValidationError(f"duplicate {field_name}: {identifier}")
            semantic_ids[type(node)].add(identifier)
    for node in module.metadata:
        _require_non_empty(node.key, "MetadataNode.key")
        _validate_json(node.value, f"metadata[{node.key!r}]")
        if node.key in metadata_keys:
            raise AstValidationError(f"duplicate metadata key: {node.key}")
        metadata_keys.add(node.key)


def _validate_unique_node_ids(nodes: tuple[Any, ...]) -> None:
    seen: set[str] = set()
    for node in nodes:
        _require_non_empty(node.node_id, f"{type(node).__name__}.node_id")
        if node.node_id in seen:
            raise AstValidationError(f"duplicate node_id: {node.node_id}")
        seen.add(node.node_id)


def _validate_imports(imports: tuple[str, ...]) -> None:
    seen: set[str] = set()
    for item in imports:
        _require_non_empty(item, "ModuleNode.imports")
        if item in seen:
            raise AstValidationError(f"duplicate import: {item}")
        seen.add(item)


def _validate_declaration(node: Any) -> None:
    if isinstance(node, GoalNode):
        _require_non_empty(node.kind, "GoalNode.kind")
        _require_non_empty(node.target, "GoalNode.target")
    elif isinstance(node, StateNode):
        _require_non_empty(node.state_id, "StateNode.state_id")
        _require_non_empty(node.state_type, "StateNode.state_type")
        _validate_json(node.data, "StateNode.data")
    elif isinstance(node, TransitionNode):
        for field_name in ("transition_id", "source", "relation", "target"):
            _require_non_empty(
                getattr(node, field_name), f"TransitionNode.{field_name}"
            )
        if (
            isinstance(node.expected_cost, bool)
            or not isinstance(node.expected_cost, (int, float))
            or not math.isfinite(node.expected_cost)
            or node.expected_cost < 0
        ):
            raise AstValidationError(
                "TransitionNode.expected_cost must be finite and non-negative"
            )
        if node.guard is not None and not isinstance(node.guard, str):
            raise AstValidationError("TransitionNode.guard must be a string or null")
        _validate_json(node.effect, "TransitionNode.effect")
    elif isinstance(node, ConstraintNode):
        for field_name in ("constraint_id", "kind", "expression"):
            _require_non_empty(
                getattr(node, field_name), f"ConstraintNode.{field_name}"
            )
    elif isinstance(node, ContextNode):
        for field_name in ("context_id", "context_type", "uri"):
            _require_non_empty(getattr(node, field_name), f"ContextNode.{field_name}")
        if not urlparse(node.uri).scheme:
            raise AstValidationError("ContextNode.uri must be an absolute URI")
    else:
        raise AstValidationError(f"unsupported AST declaration: {type(node).__name__}")


def _validate_json(value: Any, location: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AstValidationError(f"{location} must contain finite JSON numbers")
        return
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _validate_json(item, f"{location}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise AstValidationError(f"{location} object keys must be strings")
            _validate_json(item, f"{location}.{key}")
        return
    if is_dataclass(value):
        names = ", ".join(field.name for field in fields(value))
        raise AstValidationError(
            f"{location} contains runtime object {type(value).__name__}({names})"
        )
    raise AstValidationError(f"{location} is not JSON-compatible")


def _require_non_empty(value: Any, location: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AstValidationError(f"{location} must be a non-empty string")
