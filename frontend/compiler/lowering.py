from __future__ import annotations

from typing import Any

from frontend.ast import (
    ConstraintNode,
    ContextNode,
    GoalNode,
    MetadataNode,
    ModuleNode,
    StateNode,
    TransitionNode,
)

from .errors import CompilerError, CompilerErrorCode
from .injector import CompilationContext


def lower(module: ModuleNode, context: CompilationContext) -> dict[str, Any]:
    goal: GoalNode | None = None
    state: StateNode | None = None
    transitions: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []

    for node in module.declarations:
        if isinstance(node, GoalNode):
            goal = node
        elif isinstance(node, StateNode):
            state = node
        elif isinstance(node, TransitionNode):
            transition = {
                "transition_id": node.transition_id,
                "source": node.source,
                "relation": node.relation,
                "target": node.target,
                "expected_cost": node.expected_cost,
            }
            if node.guard is not None:
                transition["guard"] = node.guard
            if node.effect is not None:
                transition["effect"] = node.effect
            transitions.append(transition)
        elif isinstance(node, ConstraintNode):
            constraints.append(
                {
                    "constraint_id": node.constraint_id,
                    "kind": node.kind,
                    "expression": node.expression,
                }
            )
        elif isinstance(node, ContextNode):
            contexts.append(
                {
                    "context_id": node.context_id,
                    "context_type": node.context_type,
                    "uri": node.uri,
                }
            )
        else:
            raise CompilerError(
                CompilerErrorCode.UNSUPPORTED_NODE,
                getattr(node, "node_id", None),
                f"unsupported declaration {type(node).__name__}",
            )

    if goal is None or state is None:
        raise CompilerError(
            CompilerErrorCode.LOWERING_FAILURE,
            module.node_id,
            "validated AST did not contain goal and initial state",
        )

    result: dict[str, Any] = {
        "schema_version": "reason-ir/0.1",
        "initial_state": {
            "state_id": state.state_id,
            "state_type": state.state_type,
            "data": state.data,
        },
        "goal": {"kind": goal.kind, "target": goal.target},
        "transitions": transitions,
        "execution_policy": context.execution_policy,
        "trace_policy": context.trace_policy,
        "planner_policy": context.planner_policy,
    }
    if constraints:
        result["constraints"] = constraints
    if contexts:
        result["context_refs"] = contexts
    metadata = _metadata(module.metadata)
    if metadata:
        result["metadata"] = metadata
    return result


def _metadata(nodes: tuple[MetadataNode, ...]) -> dict[str, Any]:
    return {node.key: node.value for node in nodes}
