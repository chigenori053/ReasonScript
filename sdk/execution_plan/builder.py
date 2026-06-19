"""execution_plan.builder — construct ExecutionPlan instances programmatically."""

from __future__ import annotations

from dataclasses import dataclass, field

_SCHEMA_VERSION = "execution-plan/0.1"
_PLANNER = "reasonscript-sdk/0.1"


@dataclass(frozen=True)
class ExecutionPlan:
    name: str
    selected_steps: tuple[dict, ...] = field(default_factory=tuple)
    alternative_paths: tuple = field(default_factory=tuple)
    expected_cost: float = 0.0
    evidence_refs: tuple = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "schema_version": _SCHEMA_VERSION,
            "name": self.name,
            "selected_steps": list(self.selected_steps),
            "alternative_paths": list(self.alternative_paths),
            "expected_cost": self.expected_cost,
            "evidence_refs": list(self.evidence_refs),
            "planner_version": _PLANNER,
        }


def create_plan(name: str) -> ExecutionPlan:
    """Create an empty ExecutionPlan."""
    return ExecutionPlan(name=name)


def add_step(
    plan: ExecutionPlan,
    from_state: str | dict,
    to_state: str | dict,
    *,
    step_cost: float = 1.0,
) -> ExecutionPlan:
    """Return a new ExecutionPlan with the step appended."""
    src = from_state if isinstance(from_state, str) else from_state.get("id", str(from_state))
    dst = to_state if isinstance(to_state, str) else to_state.get("id", str(to_state))
    step_id = f"step-{len(plan.selected_steps) + 1}"
    step = {
        "step_id": step_id,
        "transition_id": f"{src}->{dst}",
        "source": src,
        "target": dst,
    }
    new_cost = plan.expected_cost + step_cost
    return ExecutionPlan(
        name=plan.name,
        selected_steps=plan.selected_steps + (step,),
        alternative_paths=plan.alternative_paths,
        expected_cost=new_cost,
        evidence_refs=plan.evidence_refs,
    )
