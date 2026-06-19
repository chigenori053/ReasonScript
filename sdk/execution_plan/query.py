"""execution_plan.query — inspect ExecutionPlan without mutation."""

from __future__ import annotations

from .builder import ExecutionPlan


def steps(plan: ExecutionPlan) -> list[str]:
    """Return human-readable step strings (does not mutate)."""
    return [
        f"{s.get('step_id')}: {s.get('source')} -> {s.get('target')}"
        for s in plan.selected_steps
    ]


def length(plan: ExecutionPlan) -> int:
    """Return the number of steps in the plan (does not mutate)."""
    return len(plan.selected_steps)
