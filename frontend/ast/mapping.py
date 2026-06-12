"""Deterministic lowering from semantic AST to Reason IR wire data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .nodes import (
    ConstraintNode,
    ContextNode,
    GoalNode,
    ModuleNode,
    StateNode,
    TransitionNode,
)
from .validation import validate


@dataclass(frozen=True)
class MappingOptions:
    planner_policy: dict[str, Any] | None = None
    execution_policy: dict[str, Any] | None = None
    trace_policy: dict[str, Any] | None = None


def to_reason_ir(
    module: ModuleNode, options: MappingOptions | None = None
) -> dict[str, Any]:
    validate(module)
    options = options or MappingOptions()
    goal = next(node for node in module.declarations if isinstance(node, GoalNode))
    state = next(node for node in module.declarations if isinstance(node, StateNode))

    result: dict[str, Any] = {
        "schema_version": "reason-ir/0.1",
        "initial_state": {
            "state_id": state.state_id,
            "state_type": state.state_type,
            "data": state.data,
        },
        "goal": {"kind": goal.kind, "target": goal.target},
        "transitions": [
            _transition(node)
            for node in module.declarations
            if isinstance(node, TransitionNode)
        ],
        "execution_policy": options.execution_policy
        or {
            "max_steps": 128,
            "rollback_on_failure": True,
            "constraint_mode": "reject",
        },
        "trace_policy": options.trace_policy
        or {
            "level": "standard",
            "include_alternatives": True,
            "include_state_data": True,
        },
    }
    contexts = [
        {
            "context_id": node.context_id,
            "context_type": node.context_type,
            "uri": node.uri,
        }
        for node in module.declarations
        if isinstance(node, ContextNode)
    ]
    constraints = [
        {
            "constraint_id": node.constraint_id,
            "kind": node.kind,
            "expression": node.expression,
        }
        for node in module.declarations
        if isinstance(node, ConstraintNode)
    ]
    metadata = {node.key: node.value for node in module.metadata}
    if contexts:
        result["context_refs"] = contexts
    if constraints:
        result["constraints"] = constraints
    if options.planner_policy is not None:
        result["planner_policy"] = options.planner_policy
    if metadata:
        result["metadata"] = metadata
    return result


def _transition(node: TransitionNode) -> dict[str, Any]:
    result = {
        "transition_id": node.transition_id,
        "source": node.source,
        "relation": node.relation,
        "target": node.target,
        "expected_cost": node.expected_cost,
    }
    if node.guard is not None:
        result["guard"] = node.guard
    if node.effect is not None:
        result["effect"] = node.effect
    return result
