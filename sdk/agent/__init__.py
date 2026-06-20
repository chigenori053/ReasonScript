"""Agent Layer Phase 1 - deterministic goal-driven agent framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from frontend.runtime_integration import (
    DiagnosticSeverity,
    ExecutionCoordinator,
    ExecutionRequest,
    PlatformDiagnostic,
    ReasoningTrace,
    RuntimeEngineRegistry,
    RuntimeValue,
    create_reasoning_trace,
    runtime_real_registry,
)
from sdk import planning
from sdk._engine import resolve_registry


SDK_VERSION = "agent-layer/0.1"
AGENT_SCHEMA = "agent-layer-agent/0.1"
TASK_SCHEMA = "agent-layer-task/0.1"
RESULT_SCHEMA = "agent-layer-result/0.1"

STATUS_SUCCESS = "Success"
STATUS_PARTIAL_SUCCESS = "PartialSuccess"
STATUS_FAILURE = "Failure"

SUPPORTED_CAPABILITIES = ("Planning", "Simulation", "Search", "Prediction")


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    capability: str
    version: str = SDK_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SDK_VERSION,
            "id": self.id,
            "name": self.name,
            "capability": self.capability,
            "version": self.version,
        }


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    capabilities: tuple[str, ...] = ("Planning",)
    configuration: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    tools: tuple[Tool, ...] = ()

    def with_tool(self, tool: Tool) -> "Agent":
        tools = tuple(item for item in self.tools if item.id != tool.id) + (tool,)
        return Agent(
            self.id,
            self.name,
            self.capabilities,
            dict(self.configuration),
            dict(self.metadata),
            tuple(sorted(tools, key=lambda item: item.id)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": AGENT_SCHEMA,
            "id": self.id,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "configuration": dict(self.configuration),
            "metadata": dict(self.metadata),
            "tools": [tool.to_dict() for tool in self.tools],
        }


@dataclass(frozen=True)
class Task:
    id: str
    description: str
    goal: planning.Goal
    priority: int = 0
    constraints: tuple[planning.PlanningConstraint, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TASK_SCHEMA,
            "id": self.id,
            "description": self.description,
            "goal": self.goal.to_dict(),
            "priority": self.priority,
            "constraints": [constraint.to_dict() for constraint in self.constraints],
        }


@dataclass(frozen=True)
class AgentContext:
    goal: planning.Goal
    world: Any = None
    reason_graph: Any = None
    planning_context: planning.PlanningContext | None = None
    constraints: tuple[planning.PlanningConstraint, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_planning_context(self) -> planning.PlanningContext:
        if self.planning_context is not None:
            constraints = _merge_constraints(self.planning_context.constraints, self.constraints)
            return planning.create_context(
                world=self.planning_context.world if self.planning_context.world is not None else self.world,
                reason_graph=(
                    self.planning_context.reason_graph
                    if self.planning_context.reason_graph is not None
                    else self.reason_graph
                ),
                execution_plan=self.planning_context.execution_plan,
                constraints=constraints,
                metadata={**self.planning_context.metadata, **self.metadata},
            )
        return planning.create_context(
            world=self.world,
            reason_graph=self.reason_graph,
            constraints=self.constraints,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SDK_VERSION,
            "goal": self.goal.to_dict(),
            "world": _plain(self.world),
            "reason_graph": _plain(self.reason_graph),
            "planning_context": self.planning_context.to_dict() if self.planning_context else None,
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Decision:
    id: str
    task: Task
    selected_plan: planning.Plan | None
    rationale: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SDK_VERSION,
            "id": self.id,
            "task": self.task.to_dict(),
            "selected_plan": self.selected_plan.to_dict() if self.selected_plan else None,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class Action:
    id: str
    action_type: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SDK_VERSION,
            "id": self.id,
            "action_type": self.action_type,
            "target": self.target,
            "parameters": _plain(self.parameters),
            "metadata": _plain(self.metadata),
        }


@dataclass(frozen=True)
class AgentTrace:
    task_events: tuple[dict[str, Any], ...] = ()
    decision_events: tuple[dict[str, Any], ...] = ()
    planning_events: tuple[dict[str, Any], ...] = ()
    action_events: tuple[dict[str, Any], ...] = ()
    execution_events: tuple[dict[str, Any], ...] = ()

    def to_reasoning_trace(self, request_id: str) -> ReasoningTrace:
        trace = create_reasoning_trace(request_id)
        for event in self.task_events:
            trace = trace.add_event("Task", str(event.get("operation", "TaskEvent")), event)
        for event in self.decision_events:
            trace = trace.add_event("Decision", str(event.get("operation", "DecisionEvent")), event)
        for event in self.planning_events:
            trace = trace.add_event("Agent", str(event.get("operation", "PlanningEvent")), event)
        for event in self.action_events:
            trace = trace.add_event("Action", str(event.get("operation", "ActionEvent")), event)
        for event in self.execution_events:
            trace = trace.add_event("Agent", str(event.get("operation", "ExecutionEvent")), event)
        return trace

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_events": list(self.task_events),
            "decision_events": list(self.decision_events),
            "planning_events": list(self.planning_events),
            "action_events": list(self.action_events),
            "execution_events": list(self.execution_events),
        }


@dataclass(frozen=True)
class AgentResult:
    status: str
    decision: Decision | None = None
    plan: planning.Plan | None = None
    actions: tuple[Action, ...] = ()
    diagnostics: tuple[PlatformDiagnostic, ...] = ()
    trace: AgentTrace = field(default_factory=AgentTrace)
    reasoning_trace: ReasoningTrace | None = None
    execution_results: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESULT_SCHEMA,
            "status": self.status,
            "decision": self.decision.to_dict() if self.decision else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "actions": [action.to_dict() for action in self.actions],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "trace": self.trace.to_dict(),
            "reasoning_trace": self.reasoning_trace.to_dict() if self.reasoning_trace else None,
            "execution_results": list(self.execution_results),
        }


def create_tool(tool_id: str, name: str, capability: str, version: str = SDK_VERSION) -> Tool:
    return Tool(tool_id, name, capability, version)


def create_agent(
    agent_id: str,
    name: str,
    *,
    capabilities: tuple[str, ...] | list[str] = ("Planning",),
    configuration: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    tools: tuple[Tool, ...] | list[Tool] = (),
) -> Agent:
    return Agent(agent_id, name, tuple(capabilities), configuration or {}, metadata or {}, tuple(tools))


def register_tool(agent: Agent, tool: Tool) -> Agent:
    return agent.with_tool(tool)


def create_task(
    task_id: str,
    description: str,
    goal: planning.Goal,
    *,
    priority: int = 0,
    constraints: tuple[planning.PlanningConstraint, ...] | list[planning.PlanningConstraint] = (),
) -> Task:
    return Task(task_id, description, goal, priority, tuple(constraints))


def create_context(
    goal: planning.Goal,
    *,
    world: Any = None,
    reason_graph: Any = None,
    planning_context: planning.PlanningContext | None = None,
    constraints: tuple[planning.PlanningConstraint, ...] | list[planning.PlanningConstraint] = (),
    metadata: dict[str, Any] | None = None,
) -> AgentContext:
    return AgentContext(goal, world, reason_graph, planning_context, tuple(constraints), metadata or {})


def decide(
    agent: Agent,
    task: Task,
    context: AgentContext,
    *,
    registry: RuntimeEngineRegistry | str | None = None,
) -> tuple[Decision | None, planning.PlanResult, tuple[PlatformDiagnostic, ...]]:
    diagnostics = validate_agent(agent) + validate_task(task) + validate_context(context)
    if diagnostics:
        return None, planning.PlanResult(planning.STATUS_FAILURE, diagnostics=diagnostics), diagnostics
    plan_result = planning.plan(task.goal, _merged_planning_context(task, context), registry=registry)
    diagnostics = tuple(plan_result.diagnostics)
    if plan_result.selected_plan is None:
        diagnostics = diagnostics or (_diagnostic("DecisionFailure", "no selectable plan was produced"),)
        return None, plan_result, diagnostics
    decision_value = Decision(
        f"decision-{task.id}",
        task,
        plan_result.selected_plan,
        "Selected highest goal satisfaction, then lowest cost, then highest confidence.",
        planning.confidence(plan_result.selected_plan),
    )
    return decision_value, plan_result, diagnostics


def plan(
    agent: Agent,
    task: Task,
    context: AgentContext,
    *,
    registry: RuntimeEngineRegistry | str | None = None,
) -> planning.PlanResult:
    del agent
    return planning.plan(task.goal, _merged_planning_context(task, context), registry=registry)


def act(decision_value: Decision) -> tuple[Action, ...]:
    if decision_value.selected_plan is None:
        return ()
    return tuple(
        Action(
            f"action-{step.step_id}",
            step.operation or "ExecutePlan",
            step.target,
            {"source": step.source, "target": step.target, "operation": step.operation},
            {"plan_id": decision_value.selected_plan.id, "step_id": step.step_id},
        )
        for step in decision_value.selected_plan.steps
    )


def execute(
    agent: Agent,
    task: Task,
    context: AgentContext,
    *,
    registry: RuntimeEngineRegistry | str | None = None,
) -> AgentResult:
    reg = resolve_registry(registry) if registry is not None else runtime_real_registry()
    decision_value, plan_result, diagnostics = decide(agent, task, context, registry=reg)
    task_events = ({"operation": "TaskReceived", "task": task.id, "agent": agent.id},)
    decision_events = (
        {"operation": "DecisionGenerated", "decision": decision_value.id if decision_value else None},
    )
    planning_events = (
        {"operation": "PlanningSDKResult", "status": plan_result.status},
    )
    if diagnostics or decision_value is None or plan_result.selected_plan is None:
        trace_value = AgentTrace(task_events, decision_events, planning_events)
        return AgentResult(
            STATUS_FAILURE,
            decision_value,
            plan_result.selected_plan,
            (),
            diagnostics,
            trace_value,
            trace_value.to_reasoning_trace(task.id),
        )

    generated_actions = act(decision_value)
    action_events = tuple(
        {"operation": "ActionGenerated", "action": action.id, "action_type": action.action_type}
        for action in generated_actions
    )
    execution_results: list[dict[str, Any]] = []
    execution_events: list[dict[str, Any]] = []
    execution_diagnostics: list[PlatformDiagnostic] = []
    coordinator = ExecutionCoordinator(reg)
    execution_plan = planning.to_execution_plan(plan_result.selected_plan)
    for action_value in generated_actions:
        request = _execution_request(task, action_value, execution_plan, reg)
        result = coordinator.execute(request)
        execution_results.append(result.to_dict())
        execution_events.append(
            {
                "operation": "ActionExecuted",
                "action": action_value.id,
                "status": result.status,
                "request_id": result.request_id,
            }
        )
        execution_diagnostics.extend(result.platform_diagnostics)
        execution_diagnostics.extend(
            _diagnostic("ExecutionFailure", item) for item in result.diagnostics
        )

    all_diagnostics = tuple(diagnostics) + tuple(execution_diagnostics)
    status_value = STATUS_SUCCESS if not all_diagnostics else STATUS_FAILURE
    trace_value = AgentTrace(
        task_events,
        decision_events,
        planning_events,
        action_events,
        tuple(execution_events),
    )
    return AgentResult(
        status_value,
        decision_value,
        plan_result.selected_plan,
        generated_actions,
        all_diagnostics,
        trace_value,
        trace_value.to_reasoning_trace(task.id),
        tuple(execution_results),
    )


def validate_agent(agent: Agent) -> tuple[PlatformDiagnostic, ...]:
    diagnostics: list[PlatformDiagnostic] = []
    if not agent.id or not agent.name:
        diagnostics.append(_diagnostic("InvalidAgent", "agent id and name are required"))
    for capability in agent.capabilities:
        if capability not in SUPPORTED_CAPABILITIES:
            diagnostics.append(_diagnostic("InvalidCapability", f"unsupported capability: {capability}"))
    if "Planning" not in agent.capabilities:
        diagnostics.append(_diagnostic("DecisionFailure", "agent requires Planning capability"))
    for tool in agent.tools:
        if tool.capability not in SUPPORTED_CAPABILITIES:
            diagnostics.append(_diagnostic("InvalidCapability", f"unsupported tool capability: {tool.capability}"))
    return tuple(diagnostics)


def validate_task(task: Task) -> tuple[PlatformDiagnostic, ...]:
    diagnostics: list[PlatformDiagnostic] = []
    if not task.id or not task.description:
        diagnostics.append(_diagnostic("InvalidTask", "task id and description are required"))
    diagnostics.extend(planning.validate_goal(task.goal))
    diagnostics.extend(planning.validate_constraints(task.constraints))
    return tuple(diagnostics)


def validate_context(context: AgentContext) -> tuple[PlatformDiagnostic, ...]:
    diagnostics = list(planning.validate_goal(context.goal))
    diagnostics.extend(planning.validate_constraints(context.constraints))
    return tuple(diagnostics)


def decision(result: AgentResult) -> Decision | None:
    return result.decision


def actions(result: AgentResult) -> tuple[Action, ...]:
    return result.actions


def status(result: AgentResult) -> str:
    return result.status


def trace(result: AgentResult) -> AgentTrace:
    return result.trace


def _merged_planning_context(task: Task, context: AgentContext) -> planning.PlanningContext:
    base = context.to_planning_context()
    constraints = _merge_constraints(base.constraints, task.constraints)
    return planning.create_context(
        world=base.world,
        reason_graph=base.reason_graph,
        execution_plan=base.execution_plan,
        constraints=constraints,
        metadata={**base.metadata, "task_id": task.id, "task_priority": task.priority},
    )


def _execution_request(
    task: Task,
    action_value: Action,
    execution_plan: dict[str, Any],
    registry: RuntimeEngineRegistry,
) -> ExecutionRequest:
    return ExecutionRequest(
        f"{task.id}:{action_value.id}",
        source_module="agent",
        reason_ir={
            "schema_version": "reason-ir/0.1",
            "metadata": {
                "runtime_operations": [
                    {"operation": "plan", "argument": action_value.target},
                ]
            },
        },
        execution_plan=execution_plan,
        runtime_registry=registry,
        metadata={
            "entry_function": "agent_action",
            "parameters": ("target",),
            "arguments": (RuntimeValue.goal(action_value.target),),
            "return_target": action_value.target,
        },
    )


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _merge_constraints(
    left: tuple[planning.PlanningConstraint, ...],
    right: tuple[planning.PlanningConstraint, ...],
) -> tuple[planning.PlanningConstraint, ...]:
    merged: dict[str, planning.PlanningConstraint] = {}
    for constraint in (*left, *right):
        merged[constraint.id] = constraint
    return tuple(merged[key] for key in sorted(merged))


def _diagnostic(code: str, message: str) -> PlatformDiagnostic:
    return PlatformDiagnostic(code, DiagnosticSeverity.ERROR, message, "Agent")


__all__ = [
    "AGENT_SCHEMA",
    "RESULT_SCHEMA",
    "SDK_VERSION",
    "SUPPORTED_CAPABILITIES",
    "TASK_SCHEMA",
    "Action",
    "Agent",
    "AgentContext",
    "AgentResult",
    "AgentTrace",
    "Decision",
    "Task",
    "Tool",
    "act",
    "actions",
    "create_agent",
    "create_context",
    "create_task",
    "create_tool",
    "decide",
    "decision",
    "execute",
    "plan",
    "register_tool",
    "status",
    "trace",
    "validate_agent",
    "validate_context",
    "validate_task",
]
