from __future__ import annotations

from dataclasses import replace

from frontend.ast import (
    ConstraintNode,
    GoalNode,
    ModuleNode,
    StateNode,
    TransitionNode,
)


def expand_defaults(module: ModuleNode) -> ModuleNode:
    """Return a canonical immutable AST with all ABI defaults materialized."""
    declarations = []
    for node in module.declarations:
        if isinstance(node, GoalNode):
            declarations.append(replace(node, kind=node.kind or "reach_state"))
        elif isinstance(node, StateNode):
            declarations.append(
                replace(
                    node,
                    state_type=node.state_type or "symbolic",
                    data={} if node.data is None else node.data,
                )
            )
        elif isinstance(node, TransitionNode):
            declarations.append(
                replace(
                    node,
                    expected_cost=(
                        1.0 if node.expected_cost is None else node.expected_cost
                    ),
                )
            )
        elif isinstance(node, ConstraintNode):
            declarations.append(replace(node, kind=node.kind or "predicate"))
        else:
            declarations.append(node)
    return replace(module, declarations=tuple(declarations))
