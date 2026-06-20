"""Planning SDK Phase 1 - deterministic goal-oriented planning layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from frontend.runtime_integration import (
    DiagnosticSeverity,
    DiagnosticSource,
    PlanningRequest,
    PlatformDiagnostic,
    ReasoningTrace,
    RuntimeEngineRegistry,
    RuntimeValue,
    create_reasoning_trace,
    runtime_value_to_plain,
)
from sdk._engine import resolve_registry


GOAL_SCHEMA = "planning-sdk-goal/0.1"
PLAN_SCHEMA = "planning-sdk-plan/0.1"
RESULT_SCHEMA = "planning-sdk-result/0.1"
SDK_VERSION = "planning-sdk/0.1"

STATUS_SUCCESS = "Success"
STATUS_PARTIAL_SUCCESS = "PartialSuccess"
STATUS_FAILURE = "Failure"


@dataclass(frozen=True)
class Goal:
    id: str
    name: str
    target_state: Any
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": GOAL_SCHEMA,
            "id": self.id,
            "name": self.name,
            "target_state": _plain(self.target_state),
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PlanningConstraint:
    id: str
    constraint_type: str
    expression: Any
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SDK_VERSION,
            "id": self.id,
            "constraint_type": self.constraint_type,
            "expression": _plain(self.expression),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PlanningContext:
    world: Any = None
    reason_graph: Any = None
    execution_plan: Any = None
    constraints: tuple[PlanningConstraint, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SDK_VERSION,
            "world": _plain(self.world),
            "reason_graph": _plain(self.reason_graph),
            "execution_plan": _plain(self.execution_plan),
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    source: str
    target: str
    operation: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "source": self.source,
            "target": self.target,
            "operation": self.operation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Plan:
    id: str
    goal: Goal
    steps: tuple[PlanStep, ...] = ()
    cost: float = 0.0
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PLAN_SCHEMA,
            "id": self.id,
            "goal": self.goal.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
            "cost": self.cost,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PlanScore:
    goal_satisfaction: float
    cost: float
    confidence: float
    constraint_satisfaction: float

    def selection_key(self) -> tuple[float, float, float]:
        return (self.goal_satisfaction * self.constraint_satisfaction, -self.cost, self.confidence)

    def to_dict(self) -> dict[str, float]:
        return {
            "goal_satisfaction": self.goal_satisfaction,
            "cost": self.cost,
            "confidence": self.confidence,
            "constraint_satisfaction": self.constraint_satisfaction,
        }


@dataclass(frozen=True)
class PlanTrace:
    planning_events: tuple[dict[str, Any], ...] = ()
    evaluation_events: tuple[dict[str, Any], ...] = ()
    selection_events: tuple[dict[str, Any], ...] = ()

    def to_reasoning_trace(self, request_id: str) -> ReasoningTrace:
        trace = create_reasoning_trace(request_id)
        for event in self.planning_events:
            trace = trace.add_event("Planning", str(event.get("operation", "PlanningEvent")), event)
        for event in self.evaluation_events:
            trace = trace.add_event("PlanEvaluation", str(event.get("operation", "PlanEvaluated")), event)
        for event in self.selection_events:
            trace = trace.add_event("PlanSelection", str(event.get("operation", "PlanSelected")), event)
        return trace

    def to_dict(self) -> dict[str, Any]:
        return {
            "planning_events": list(self.planning_events),
            "evaluation_events": list(self.evaluation_events),
            "selection_events": list(self.selection_events),
        }


@dataclass(frozen=True)
class PlanResult:
    status: str
    selected_plan: Plan | None = None
    candidate_plans: tuple[Plan, ...] = ()
    diagnostics: tuple[PlatformDiagnostic, ...] = ()
    trace: PlanTrace = field(default_factory=PlanTrace)
    reasoning_trace: ReasoningTrace | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESULT_SCHEMA,
            "status": self.status,
            "selected_plan": self.selected_plan.to_dict() if self.selected_plan else None,
            "candidate_plans": [plan.to_dict() for plan in self.candidate_plans],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "trace": self.trace.to_dict(),
            "reasoning_trace": self.reasoning_trace.to_dict() if self.reasoning_trace else None,
        }


class Planner:
    def __init__(self, registry: RuntimeEngineRegistry | str | None = None) -> None:
        self.registry = resolve_registry(registry)

    def plan(self, goal: Goal, context: PlanningContext | None = None) -> PlanResult:
        context = context or PlanningContext()
        diagnostics = list(validate_goal(goal))
        diagnostics.extend(validate_constraints(context.constraints))
        if diagnostics:
            trace = PlanTrace(planning_events=({"operation": "ValidationFailed", "goal": goal.id},))
            return PlanResult(
                STATUS_FAILURE,
                None,
                (),
                tuple(diagnostics),
                trace,
                trace.to_reasoning_trace(goal.id),
            )
        if self.registry.planning_engine is None:
            diagnostic = _diagnostic("PlanningFailure", "runtime planning engine is unavailable")
            trace = PlanTrace(planning_events=({"operation": "RuntimeUnavailable", "goal": goal.id},))
            return PlanResult(STATUS_FAILURE, None, (), (diagnostic,), trace, trace.to_reasoning_trace(goal.id))

        runtime_result = self.registry.planning_engine.plan(PlanningRequest(RuntimeValue.goal(goal.name)))
        candidates = _candidate_plans(goal, context, runtime_result)
        evaluations = tuple((candidate, self.evaluate(candidate, context)) for candidate in candidates)
        selected = self.select(tuple(candidate for candidate, _ in evaluations), context)
        status = STATUS_SUCCESS if selected is not None else STATUS_FAILURE
        trace = PlanTrace(
            planning_events=(
                {"operation": "RuntimePlan", "goal": goal.id, "runtime_trace": list(runtime_result.trace)},
                {"operation": "CandidatePlansGenerated", "count": len(candidates)},
            ),
            evaluation_events=(
                *(
                    {"operation": "PlanEvaluated", "plan": candidate.id, "score": score.to_dict()}
                    for candidate, score in evaluations
                ),
            ),
            selection_events=(
                {"operation": "PlanSelected", "plan": selected.id if selected else None},
            ),
        )
        diagnostics = list(_diagnostic("PlanningFailure", item) for item in runtime_result.diagnostics)
        if selected is None:
            for candidate in candidates:
                diagnostics.extend(self.validate(candidate, context))
        if diagnostics and selected is None:
            status = STATUS_FAILURE
        return PlanResult(status, selected, candidates, tuple(diagnostics), trace, trace.to_reasoning_trace(goal.id))

    def evaluate(self, plan: Plan, context: PlanningContext | None = None) -> PlanScore:
        context = context or PlanningContext()
        goal_satisfaction = 1.0 if goal_satisfied(plan) else 0.0
        constraint_satisfaction = 1.0 if not validate_constraints_for_plan(plan, context.constraints) else 0.0
        return PlanScore(goal_satisfaction, cost(plan), confidence(plan), constraint_satisfaction)

    def validate(self, plan: Plan, context: PlanningContext | None = None) -> tuple[PlatformDiagnostic, ...]:
        context = context or PlanningContext()
        return validate_plan(plan) + validate_constraints_for_plan(plan, context.constraints)

    def select(self, plans: tuple[Plan, ...], context: PlanningContext | None = None) -> Plan | None:
        valid = [plan for plan in plans if not self.validate(plan, context)]
        if not valid:
            return None
        return sorted(
            valid,
            key=lambda item: (
                self.evaluate(item, context).selection_key(),
                item.goal.priority,
                item.id,
            ),
            reverse=True,
        )[0]


def create_goal(
    goal_id: str,
    name: str,
    target_state: Any,
    *,
    priority: int = 0,
    metadata: dict[str, Any] | None = None,
) -> Goal:
    return Goal(goal_id, name, target_state, priority, metadata or {})


def create_constraint(
    constraint_id: str,
    constraint_type: str,
    expression: Any,
    *,
    metadata: dict[str, Any] | None = None,
) -> PlanningConstraint:
    return PlanningConstraint(constraint_id, constraint_type, expression, metadata or {})


def create_context(
    *,
    world: Any = None,
    reason_graph: Any = None,
    execution_plan: Any = None,
    constraints: tuple[PlanningConstraint, ...] | list[PlanningConstraint] = (),
    metadata: dict[str, Any] | None = None,
) -> PlanningContext:
    return PlanningContext(world, reason_graph, execution_plan, tuple(constraints), metadata or {})


def plan(goal: Goal, context: PlanningContext | None = None, *, registry: RuntimeEngineRegistry | str | None = None) -> PlanResult:
    return Planner(registry).plan(goal, context)


def evaluate_plan(plan_value: Plan, context: PlanningContext | None = None) -> PlanScore:
    return Planner().evaluate(plan_value, context)


def validate_plan(plan_value: Plan) -> tuple[PlatformDiagnostic, ...]:
    diagnostics: list[PlatformDiagnostic] = []
    if not plan_value.id:
        diagnostics.append(_diagnostic("InvalidPlan", "plan id is required"))
    if not plan_value.steps:
        diagnostics.append(_diagnostic("GoalUnreachable", "plan has no reachable steps"))
    seen: set[str] = set()
    for step in plan_value.steps:
        if not step.step_id:
            diagnostics.append(_diagnostic("InvalidPlan", "plan step id is required"))
        if step.step_id in seen:
            diagnostics.append(_diagnostic("InvalidPlan", f"duplicate step: {step.step_id}"))
        seen.add(step.step_id)
        if not step.source or not step.target:
            diagnostics.append(_diagnostic("InvalidPlan", f"unreachable step: {step.step_id}"))
    for left, right in zip(plan_value.steps, plan_value.steps[1:]):
        if left.target != right.source:
            diagnostics.append(_diagnostic("InvalidPlan", f"plan continuity broken at {right.step_id}"))
    return tuple(diagnostics)


def validate_goal(goal: Goal) -> tuple[PlatformDiagnostic, ...]:
    diagnostics: list[PlatformDiagnostic] = []
    if not goal.id:
        diagnostics.append(_diagnostic("InvalidGoal", "goal id is required"))
    if not goal.name:
        diagnostics.append(_diagnostic("InvalidGoal", "goal name is required"))
    if goal.target_state in (None, ""):
        diagnostics.append(_diagnostic("GoalUnreachable", "goal target_state is required"))
    return tuple(diagnostics)


def validate_constraints(constraints: tuple[PlanningConstraint, ...]) -> tuple[PlatformDiagnostic, ...]:
    diagnostics: list[PlatformDiagnostic] = []
    for constraint in constraints:
        if not constraint.id or not constraint.constraint_type:
            diagnostics.append(_diagnostic("ConstraintViolation", "constraint id and type are required"))
    return tuple(diagnostics)


def validate_constraints_for_plan(
    plan_value: Plan,
    constraints: tuple[PlanningConstraint, ...],
) -> tuple[PlatformDiagnostic, ...]:
    diagnostics: list[PlatformDiagnostic] = []
    for constraint in constraints:
        if constraint.constraint_type == "MaximumSteps" and len(plan_value.steps) > int(constraint.expression):
            diagnostics.append(_diagnostic("ConstraintViolation", f"maximum steps exceeded: {constraint.id}"))
        if constraint.constraint_type == "CostLimit" and plan_value.cost > float(constraint.expression):
            diagnostics.append(_diagnostic("ConstraintViolation", f"cost limit exceeded: {constraint.id}"))
        if constraint.constraint_type == "AvoidState":
            states = {step.source for step in plan_value.steps} | {step.target for step in plan_value.steps}
            if str(constraint.expression) in states:
                diagnostics.append(_diagnostic("ConstraintViolation", f"avoid state violated: {constraint.id}"))
        if constraint.constraint_type == "RequireState":
            states = {step.source for step in plan_value.steps} | {step.target for step in plan_value.steps}
            if str(constraint.expression) not in states:
                diagnostics.append(_diagnostic("ConstraintViolation", f"required state missing: {constraint.id}"))
    return tuple(diagnostics)


def to_execution_plan(plan_value: Plan) -> dict[str, Any]:
    return {
        "schema_version": "execution-plan/0.1",
        "name": plan_value.id,
        "selected_steps": [
            {
                "step_id": step.step_id,
                "transition_id": step.operation,
                "source": step.source,
                "target": step.target,
            }
            for step in plan_value.steps
        ],
        "alternative_paths": [],
        "expected_cost": plan_value.cost,
        "evidence_refs": [f"{plan_value.id}:trace"],
        "planner_version": SDK_VERSION,
    }


def steps(plan_value: Plan) -> tuple[PlanStep, ...]:
    return plan_value.steps


def cost(plan_value: Plan) -> float:
    return float(plan_value.cost)


def confidence(plan_value: Plan) -> float:
    return float(plan_value.confidence)


def goal(plan_value: Plan) -> Goal:
    return plan_value.goal


def goal_satisfied(plan_value: Plan) -> bool:
    target = _state_id(plan_value.goal.target_state)
    return bool(plan_value.steps) and plan_value.steps[-1].target == target


def _candidate_plans(goal_value: Goal, context: PlanningContext, runtime_result: Any) -> tuple[Plan, ...]:
    execution_plan = runtime_result.execution_plan or _plain(context.execution_plan) or {}
    runtime_cost = _runtime_cost(runtime_result)
    steps = _steps_from_execution_plan(execution_plan)
    if not steps:
        source = _initial_state(context)
        target = _state_id(goal_value.target_state)
        steps = (PlanStep("step-1", source, target, "runtime.plan"),)
    primary = Plan(
        f"plan-{goal_value.id}-1",
        goal_value,
        steps,
        float(execution_plan.get("expected_cost", runtime_cost)),
        _runtime_confidence(runtime_result),
        {"runtime_trace": list(runtime_result.trace), "source": "runtime.plan"},
    )
    return (primary,)


def _steps_from_execution_plan(execution_plan: dict[str, Any]) -> tuple[PlanStep, ...]:
    result: list[PlanStep] = []
    for index, step in enumerate(execution_plan.get("selected_steps", []) or []):
        result.append(
            PlanStep(
                str(step.get("step_id", f"step-{index + 1}")),
                str(step.get("source", "")),
                str(step.get("target", "")),
                str(step.get("transition_id", step.get("operation", "runtime.plan"))),
                {"execution_plan": dict(step)},
            )
        )
    return tuple(result)


def _runtime_cost(runtime_result: Any) -> float:
    plain = runtime_value_to_plain(runtime_result.value) if getattr(runtime_result, "value", None) is not None else {}
    if isinstance(plain, dict) and "cost" in plain:
        return float(plain["cost"])
    return 1.0


def _runtime_confidence(runtime_result: Any) -> float:
    plain = runtime_value_to_plain(runtime_result.value) if getattr(runtime_result, "value", None) is not None else {}
    if isinstance(plain, dict) and "confidence" in plain:
        return float(plain["confidence"])
    return 1.0


def _initial_state(context: PlanningContext) -> str:
    if isinstance(context.metadata.get("initial_state"), str):
        return context.metadata["initial_state"]
    graph = _plain(context.reason_graph)
    if isinstance(graph, dict) and graph.get("nodes"):
        return str(graph["nodes"][0].get("id", "start"))
    return "start"


def _state_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id", value.get("name", value)))
    if hasattr(value, "id"):
        return str(value.id)
    return str(value)


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, RuntimeValue):
        return runtime_value_to_plain(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _diagnostic(code: str, message: str) -> PlatformDiagnostic:
    return PlatformDiagnostic(code, DiagnosticSeverity.ERROR, message, DiagnosticSource.RUNTIME)


__all__ = [
    "GOAL_SCHEMA",
    "PLAN_SCHEMA",
    "RESULT_SCHEMA",
    "SDK_VERSION",
    "Goal",
    "Plan",
    "PlanResult",
    "PlanScore",
    "PlanStep",
    "PlanTrace",
    "Planner",
    "PlanningConstraint",
    "PlanningContext",
    "confidence",
    "cost",
    "create_constraint",
    "create_context",
    "create_goal",
    "evaluate_plan",
    "goal",
    "goal_satisfied",
    "plan",
    "steps",
    "to_execution_plan",
    "validate_constraints",
    "validate_goal",
    "validate_plan",
]
