"""Language-neutral semantic AST node definitions."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Mapping, TypeAlias

AST_VERSION = "reasonscript-ast/0.1"
JsonValue: TypeAlias = Any


@dataclass(frozen=True)
class GoalNode:
    node_id: str
    kind: str
    target: str


@dataclass(frozen=True)
class StateNode:
    node_id: str
    state_id: str
    state_type: str
    data: JsonValue


@dataclass(frozen=True)
class TransitionNode:
    node_id: str
    transition_id: str
    source: str
    relation: str
    target: str
    expected_cost: float = 1.0
    guard: str | None = None
    effect: JsonValue = None


@dataclass(frozen=True)
class ConstraintNode:
    node_id: str
    constraint_id: str
    kind: str
    expression: str


@dataclass(frozen=True)
class ContextNode:
    node_id: str
    context_id: str
    context_type: str
    uri: str


@dataclass(frozen=True)
class MetadataNode:
    node_id: str
    key: str
    value: JsonValue


Declaration: TypeAlias = (
    GoalNode | StateNode | TransitionNode | ConstraintNode | ContextNode
)


@dataclass(frozen=True)
class ModuleNode:
    node_id: str
    version: str = AST_VERSION
    imports: tuple[str, ...] = ()
    declarations: tuple[Declaration, ...] = ()
    metadata: tuple[MetadataNode, ...] = ()


def to_json_value(value: Any) -> JsonValue:
    """Return the AST as a JSON-compatible value without implementation tags."""
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            field.name: to_json_value(getattr(value, field.name)) for field in fields(value)
        }
        if not isinstance(value, ModuleNode):
            result["node_type"] = type(value).__name__
        else:
            result["node_type"] = "ModuleNode"
        return result
    if isinstance(value, Mapping):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_json_value(item) for item in value]
    return value


def from_json_value(value: Mapping[str, Any]) -> ModuleNode:
    """Construct an immutable semantic AST from its versioned wire form."""
    if value.get("node_type") != "ModuleNode":
        raise ValueError("AST root must have node_type ModuleNode")
    declarations = tuple(_declaration(item) for item in value.get("declarations", ()))
    metadata = tuple(
        MetadataNode(item["node_id"], item["key"], item["value"])
        for item in value.get("metadata", ())
        if _expect_node_type(item, "MetadataNode")
    )
    return ModuleNode(
        node_id=value["node_id"],
        version=value["version"],
        imports=tuple(value.get("imports", ())),
        declarations=declarations,
        metadata=metadata,
    )


def _declaration(value: Mapping[str, Any]) -> Declaration:
    node_type = value.get("node_type")
    if node_type == "GoalNode":
        return GoalNode(value["node_id"], value["kind"], value["target"])
    if node_type == "StateNode":
        return StateNode(
            value["node_id"], value["state_id"], value["state_type"], value["data"]
        )
    if node_type == "TransitionNode":
        return TransitionNode(
            value["node_id"],
            value["transition_id"],
            value["source"],
            value["relation"],
            value["target"],
            value.get("expected_cost", 1.0),
            value.get("guard"),
            value.get("effect"),
        )
    if node_type == "ConstraintNode":
        return ConstraintNode(
            value["node_id"],
            value["constraint_id"],
            value["kind"],
            value["expression"],
        )
    if node_type == "ContextNode":
        return ContextNode(
            value["node_id"],
            value["context_id"],
            value["context_type"],
            value["uri"],
        )
    raise ValueError(f"unsupported AST node_type: {node_type}")


def _expect_node_type(value: Mapping[str, Any], expected: str) -> bool:
    if value.get("node_type") != expected:
        raise ValueError(f"expected node_type {expected}")
    return True
