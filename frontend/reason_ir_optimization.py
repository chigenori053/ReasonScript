"""Conservative deterministic optimizations for Reason IR expressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PureReasonFunction:
    name: str
    instruction_count: int
    recursive: bool = False
    has_io: bool = False
    mutates_global: bool = False
    changes_external_state: bool = False
    writes_artifact: bool = False
    nondeterministic: bool = False

    @property
    def eligible_for_fast_path(self) -> bool:
        return (
            self.instruction_count <= 32
            and not self.recursive
            and not self.has_io
            and not self.mutates_global
            and not self.changes_external_state
            and not self.writes_artifact
            and not self.nondeterministic
        )


def constant_fold(expression: Mapping[str, Any]) -> dict[str, Any]:
    """Fold a numeric binary IR node only when both operands are literals."""
    left, right = expression.get("left"), expression.get("right")
    operator = expression.get("operator")
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return dict(expression)
    operations = {"+": lambda: left + right, "-": lambda: left - right, "*": lambda: left * right, "/": lambda: left / right if right != 0 else None}
    if operator not in operations:
        return dict(expression)
    value = operations[operator]()
    return {"kind": "literal", "value": value} if value is not None else dict(expression)


def is_loop_invariant(expression: Mapping[str, Any], mutated_names: set[str]) -> bool:
    """Reject nodes with effects, observations, or reads of loop-mutated names."""
    if expression.get("side_effect") or expression.get("observation_dependency"):
        return False
    if expression.get("kind") == "identifier":
        return expression.get("name") not in mutated_names
    return all(is_loop_invariant(item, mutated_names) for item in expression.get("children", ()))
