"""Small executable reference model for the normative v0.1 semantics."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class Goal:
    kind: str
    target: str


@dataclass(frozen=True)
class State:
    state_id: str
    state_type: str
    data: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def from_mapping(
        cls, state_id: str, state_type: str, data: Mapping[str, Any]
    ) -> "State":
        return cls(state_id, state_type, tuple(sorted(data.items())))


@dataclass(frozen=True)
class Transition:
    transition_id: str
    source: str
    target: str
    expected_cost: float = 0.0


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
    planner_version: str = "reference-planner/0.1"


@dataclass(frozen=True)
class StateDelta:
    delta_id: str
    before_state: State
    after_state: State
    applied_transition: str


Constraint = Callable[[State, Transition], bool]


class PlanningFailure(ValueError):
    pass


class ExecutionFailure(ValueError):
    pass


def goal_satisfied(goal: Goal, state: State) -> bool:
    if goal.kind != "reach_state":
        raise PlanningFailure(f"unsupported goal kind: {goal.kind}")
    return state.state_id == goal.target


def plan(
    initial_state: State,
    goal: Goal,
    transitions: Iterable[Transition],
    *,
    max_depth: int = 128,
    constraint: Constraint | None = None,
) -> ExecutionPlan:
    if goal_satisfied(goal, initial_state):
        return ExecutionPlan((), 0.0)

    rules = tuple(transitions)
    for rule in rules:
        if rule.expected_cost < 0:
            raise PlanningFailure("transition cost must be non-negative")

    queue: list[tuple[float, int, tuple[str, ...], str, tuple[Transition, ...]]] = [
        (0.0, 0, (), initial_state.state_id, ())
    ]
    best: dict[str, tuple[float, int, tuple[str, ...]]] = {}

    while queue:
        cost, depth, ids, current, path = heapq.heappop(queue)
        key = (cost, depth, ids)
        if current in best and best[current] <= key:
            continue
        best[current] = key
        if current == goal.target:
            steps = tuple(
                PlanStep(
                    step_id=f"step-{index + 1}",
                    transition_id=rule.transition_id,
                    source=rule.source,
                    target=rule.target,
                )
                for index, rule in enumerate(path)
            )
            return ExecutionPlan(steps, cost)
        if depth >= max_depth:
            continue

        outgoing = sorted(
            (rule for rule in rules if rule.source == current),
            key=lambda rule: rule.transition_id,
        )
        current_state = State(current, initial_state.state_type)
        for rule in outgoing:
            if constraint is not None and not constraint(current_state, rule):
                continue
            next_ids = ids + (rule.transition_id,)
            heapq.heappush(
                queue,
                (
                    cost + rule.expected_cost,
                    depth + 1,
                    next_ids,
                    rule.target,
                    path + (rule,),
                ),
            )

    raise PlanningFailure("no valid path to goal within planning bounds")


def execute(
    initial_state: State,
    goal: Goal,
    transitions: Iterable[Transition],
    execution_plan: ExecutionPlan,
    *,
    constraint: Constraint | None = None,
) -> tuple[State, tuple[StateDelta, ...]]:
    rules = {rule.transition_id: rule for rule in transitions}
    current = initial_state
    deltas: list[StateDelta] = []

    for index, step in enumerate(execution_plan.selected_steps):
        try:
            rule = rules[step.transition_id]
        except KeyError as error:
            raise ExecutionFailure("plan references an unknown transition") from error
        if (
            current.state_id != step.source
            or rule.source != step.source
            or rule.target != step.target
        ):
            raise ExecutionFailure("plan step does not match current state or transition")
        if constraint is not None and not constraint(current, rule):
            raise ExecutionFailure("constraint rejected before commit")

        after = State(rule.target, current.state_type, current.data)
        deltas.append(
            StateDelta(
                delta_id=f"delta-{index + 1}",
                before_state=current,
                after_state=after,
                applied_transition=rule.transition_id,
            )
        )
        current = after

    if not goal_satisfied(goal, current):
        raise ExecutionFailure("plan terminated without satisfying goal")
    return current, tuple(deltas)


def rollback(delta: StateDelta, delta_id: str) -> StateDelta:
    return StateDelta(
        delta_id=delta_id,
        before_state=delta.after_state,
        after_state=delta.before_state,
        applied_transition=f"rollback:{delta.applied_transition}",
    )
