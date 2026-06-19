"""execution_plan.validation — validate ExecutionPlan ABI compliance."""

from __future__ import annotations

from .builder import ExecutionPlan, _SCHEMA_VERSION


def validate(plan: ExecutionPlan | dict) -> bool:
    """Validate an ExecutionPlan for ABI compliance.

    Checks:
    - Step continuity (target of step N == source of step N+1)
    - State existence (source/target non-empty)
    - Plan compatibility (schema_version)
    - ExecutionPlan ABI (selected_steps, expected_cost)
    """
    if isinstance(plan, dict):
        return _validate_dict(plan)
    return _validate_dict(plan.to_dict())


def _validate_dict(d: dict) -> bool:
    if d.get("schema_version") != _SCHEMA_VERSION:
        return False
    steps = d.get("selected_steps")
    if not isinstance(steps, list):
        return False
    if "expected_cost" not in d:
        return False

    for step in steps:
        if not step.get("source") or not step.get("target"):
            return False
        if not step.get("step_id"):
            return False

    # Step continuity
    for i in range(len(steps) - 1):
        if steps[i].get("target") != steps[i + 1].get("source"):
            return False

    return True
