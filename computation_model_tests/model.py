"""Executable witness model for mathematical state-transition computation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class MathState:
    state_id: str
    state_type: str
    _data_json: str

    @classmethod
    def create(
        cls, state_id: str, data: Mapping[str, Any], state_type: str = "mathematical"
    ) -> "MathState":
        return cls(state_id, state_type, _canonical(data))

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self._data_json)

    def as_snapshot(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "state_type": self.state_type,
            "data": self.data,
        }


Effect = Callable[[dict[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class MathTransition:
    transition_id: str
    source: str
    target: str
    relation: str
    effect: Effect
    expected_cost: float = 1.0


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    transition_id: str
    source: str
    target: str


@dataclass(frozen=True)
class ExecutionPlan:
    selected_steps: tuple[PlanStep, ...]
    expected_cost: float
    planner_version: str = "computation-witness-planner/0.1"


@dataclass(frozen=True)
class StateDelta:
    delta_id: str
    before_state: MathState
    after_state: MathState
    applied_transition: str


@dataclass(frozen=True)
class InferenceResult:
    status: str
    final_state: MathState
    state_deltas: tuple[StateDelta, ...]
    proof_step_ids: tuple[str, ...]
    trace_id: str


def make_plan(transitions: Iterable[MathTransition]) -> ExecutionPlan:
    rules = tuple(transitions)
    if any(rule.expected_cost < 0 for rule in rules):
        raise ValueError("transition cost must be non-negative")
    for left, right in zip(rules, rules[1:]):
        if left.target != right.source:
            raise ValueError("transition procedure is not a continuous chain")
    return ExecutionPlan(
        selected_steps=tuple(
            PlanStep(
                step_id=f"step-{index}",
                transition_id=rule.transition_id,
                source=rule.source,
                target=rule.target,
            )
            for index, rule in enumerate(rules, 1)
        ),
        expected_cost=sum(rule.expected_cost for rule in rules),
    )


def execute(
    initial_state: MathState,
    goal_state_id: str,
    transitions: Iterable[MathTransition],
    plan: ExecutionPlan,
    *,
    trace_id: str = "computation-validation-trace",
) -> InferenceResult:
    rules = {rule.transition_id: rule for rule in transitions}
    current = initial_state
    deltas: list[StateDelta] = []

    for index, step in enumerate(plan.selected_steps, 1):
        rule = rules[step.transition_id]
        if (
            current.state_id != step.source
            or rule.source != step.source
            or rule.target != step.target
        ):
            raise ValueError("plan step does not match current state")
        candidate_data = rule.effect(current.data)
        candidate = MathState.create(rule.target, candidate_data, current.state_type)
        deltas.append(
            StateDelta(
                delta_id=f"delta-{index}",
                before_state=current,
                after_state=candidate,
                applied_transition=rule.transition_id,
            )
        )
        current = candidate

    if current.state_id != goal_state_id:
        raise ValueError("execution did not satisfy the goal")
    return InferenceResult(
        status="completed",
        final_state=current,
        state_deltas=tuple(deltas),
        proof_step_ids=tuple(step.step_id for step in plan.selected_steps),
        trace_id=trace_id,
    )


def run_procedure(
    initial_state: MathState,
    goal_state_id: str,
    transitions: Iterable[MathTransition],
) -> tuple[ExecutionPlan, InferenceResult]:
    rules = tuple(transitions)
    plan = make_plan(rules)
    return plan, execute(initial_state, goal_state_id, rules, plan)


def project(result: InferenceResult, policy: str) -> Any:
    data = result.final_state.data
    if policy == "numeric":
        return data["numeric"]
    if policy == "rational":
        return data["rational"]
    if policy == "symbolic":
        return data["symbolic"]
    if policy == "state":
        return {"state_id": result.final_state.state_id}
    if policy == "proof":
        return [
            {
                "transition_id": delta.applied_transition,
                "before": delta.before_state.state_id,
                "after": delta.after_state.state_id,
            }
            for delta in result.state_deltas
        ]
    raise ValueError(f"unknown output policy: {policy}")


def plan_as_dto(plan: ExecutionPlan) -> dict[str, Any]:
    return {
        "selected_steps": [
            {
                "step_id": step.step_id,
                "transition_id": step.transition_id,
                "source": step.source,
                "target": step.target,
            }
            for step in plan.selected_steps
        ],
        "alternative_paths": [],
        "expected_cost": plan.expected_cost,
        "evidence_refs": [],
        "planner_version": plan.planner_version,
    }


def result_as_dto(result: InferenceResult) -> dict[str, Any]:
    deltas = [
        {
            "delta_id": delta.delta_id,
            "before_state": delta.before_state.as_snapshot(),
            "after_state": delta.after_state.as_snapshot(),
            "applied_transition": delta.applied_transition,
            "timestamp": index,
        }
        for index, delta in enumerate(result.state_deltas, 1)
    ]
    return {
        "status": result.status,
        "final_state": result.final_state.as_snapshot(),
        "state_deltas": deltas,
        "proof": {
            "selected_step_ids": list(result.proof_step_ids),
            "evidence_refs": [],
        },
        "violations": [],
        "alternatives": [],
        "trace_id": result.trace_id,
    }


def assert_valid_delta_chain(testcase: Any, result: InferenceResult) -> None:
    for left, right in zip(result.state_deltas, result.state_deltas[1:]):
        testcase.assertEqual(left.after_state, right.before_state)
    testcase.assertEqual(result.final_state, result.state_deltas[-1].after_state)
