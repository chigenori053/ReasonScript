from __future__ import annotations

import math
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping

REASON_IR_VERSION = "reason-ir/0.1"
JsonValue = Any


@dataclass(frozen=True)
class StateSnapshot:
    state_id: str
    state_type: str
    data: JsonValue

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> StateSnapshot:
        return cls(value["state_id"], value["state_type"], value["data"])


@dataclass(frozen=True)
class GoalSpec:
    kind: str
    target: str


@dataclass(frozen=True)
class ContextRef:
    context_id: str
    context_type: str
    uri: str | None = None


@dataclass(frozen=True)
class ConstraintSpec:
    constraint_id: str
    kind: str
    expression: str


@dataclass(frozen=True)
class TransitionSpec:
    transition_id: str
    source: str
    relation: str
    target: str
    expected_cost: float
    guard: str | None = None
    effect: JsonValue = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TransitionSpec:
        return cls(
            value["transition_id"],
            value["source"],
            value["relation"],
            value["target"],
            value["expected_cost"],
            value.get("guard"),
            value.get("effect"),
        )


@dataclass(frozen=True)
class PlannerPolicy:
    strategy: str = "minimum_expected_cost"
    max_depth: int | None = 128
    max_alternatives: int | None = 8


@dataclass(frozen=True)
class ExecutionPolicy:
    max_steps: int = 128
    rollback_on_failure: bool = True
    constraint_mode: str = "reject"


@dataclass(frozen=True)
class TracePolicy:
    level: str = "standard"
    include_alternatives: bool = True
    include_state_data: bool = True


@dataclass(frozen=True)
class ReasonIR:
    schema_version: str
    initial_state: StateSnapshot
    goal: GoalSpec
    transitions: tuple[TransitionSpec, ...]
    execution_policy: ExecutionPolicy
    trace_policy: TracePolicy
    context_refs: tuple[ContextRef, ...] = ()
    constraints: tuple[ConstraintSpec, ...] = ()
    planner_policy: PlannerPolicy | None = None
    metadata: Mapping[str, JsonValue] | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ReasonIR:
        version = value.get("schema_version")
        if version != REASON_IR_VERSION:
            raise ValueError(f"unsupported Reason IR version: {version}")
        required = (
            "initial_state",
            "goal",
            "transitions",
            "execution_policy",
            "trace_policy",
        )
        missing = [field for field in required if field not in value]
        if missing:
            raise ValueError(f"missing required field: {missing[0]}")
        transition_ids: set[str] = set()
        transitions = []
        for item in value["transitions"]:
            transition = TransitionSpec.from_dict(item)
            if transition.transition_id in transition_ids:
                raise ValueError(f"duplicate transition_id: {transition.transition_id}")
            if not math.isfinite(transition.expected_cost) or transition.expected_cost < 0:
                raise ValueError("expected_cost must be finite and non-negative")
            transition_ids.add(transition.transition_id)
            transitions.append(transition)
        planner = value.get("planner_policy")
        return cls(
            version,
            StateSnapshot.from_dict(value["initial_state"]),
            GoalSpec(**value["goal"]),
            tuple(transitions),
            ExecutionPolicy(**value["execution_policy"]),
            TracePolicy(**value["trace_policy"]),
            tuple(ContextRef(**item) for item in value.get("context_refs", [])),
            tuple(ConstraintSpec(**item) for item in value.get("constraints", [])),
            PlannerPolicy(**planner) if planner is not None else None,
            dict(value.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        value = _wire(self)
        for field in ("context_refs", "constraints"):
            if not value[field]:
                value.pop(field)
        if value["planner_policy"] is None:
            value.pop("planner_policy")
        if not value["metadata"]:
            value.pop("metadata")
        return value


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    transition_id: str
    source: str
    target: str


@dataclass(frozen=True)
class PlanPath:
    step_ids: tuple[str, ...]
    expected_cost: float


@dataclass(frozen=True)
class ExecutionPlan:
    selected_steps: tuple[PlanStep, ...]
    alternative_paths: tuple[PlanPath, ...]
    expected_cost: float
    evidence_refs: tuple[str, ...]
    planner_version: str


@dataclass(frozen=True)
class StateDelta:
    delta_id: str
    before_state: StateSnapshot
    after_state: StateSnapshot
    applied_transition: str
    timestamp: int

    def __post_init__(self) -> None:
        if not 0 <= self.timestamp <= 2**64 - 1:
            raise ValueError("timestamp must be uint64")


class InferenceStatus(str, Enum):
    COMPLETED = "completed"
    REJECTED = "rejected"
    DECISION_REQUIRED = "decision_required"
    FAILED = "failed"


@dataclass(frozen=True)
class Proof:
    selected_step_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class Violation:
    constraint_id: str
    message: str


@dataclass(frozen=True)
class InferenceResult:
    status: InferenceStatus
    final_state: StateSnapshot
    state_deltas: tuple[StateDelta, ...]
    proof: Proof | None
    violations: tuple[Violation, ...]
    alternatives: tuple[PlanPath, ...]
    trace_id: str


@dataclass(frozen=True)
class TraceEvent:
    event_type: str
    payload: Mapping[str, JsonValue]

    def to_dict(self) -> dict[str, Any]:
        return {"event_type": self.event_type, **self.payload}


@dataclass(frozen=True)
class Trace:
    request_id: str
    reason_ir_version: str
    planner_version: str | None
    policy_version: str
    events: tuple[TraceEvent, ...]


class TransactionStatus(str, Enum):
    PREPARED = "prepared"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class TransactionRecord:
    transaction_id: str
    execution_plan_id: str
    candidate_id: str
    delta_id: str | None
    status: TransactionStatus
    commit_timestamp: int | None
    validation_failures: tuple[str, ...]
    source_delta_id: str | None

    def __post_init__(self) -> None:
        if self.commit_timestamp is not None and not 0 <= self.commit_timestamp <= 2**64 - 1:
            raise ValueError("commit_timestamp must be uint64")


def _wire(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, TraceEvent):
        return value.to_dict()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _wire(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: _wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_wire(item) for item in value]
    return value


def to_dict(value: Any) -> dict[str, Any]:
    """Convert any public DTO to its JSON-compatible wire representation."""
    result = _wire(value)
    if not isinstance(result, dict):
        raise TypeError("DTO must serialize to a JSON object")
    return result
