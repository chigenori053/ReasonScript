"""Language-neutral conformance helpers for the reason-ir/0.1 ABI."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
ABI_VERSION = "reason-ir/0.1"


class ConformanceError(ValueError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_reason_ir(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_reason_ir(value)
    for transition in normalized["transitions"]:
        if transition.get("guard") is None:
            transition.pop("guard", None)
        if transition.get("effect") is None:
            transition.pop("effect", None)
    for context in normalized["context_refs"]:
        if context.get("uri") is None:
            context.pop("uri", None)
    return normalized


def validate_reason_ir(value: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "initial_state",
        "goal",
        "transitions",
        "execution_policy",
        "trace_policy",
    }
    missing = sorted(required - value.keys())
    if missing:
        raise ConformanceError(f"missing required field: {missing[0]}")
    if value["schema_version"] != ABI_VERSION:
        raise ConformanceError(f"unsupported ABI version: {value['schema_version']}")
    _require_object(value["initial_state"], "initial_state")
    _require_fields(value["initial_state"], ("state_id", "state_type", "data"), "initial_state")
    _require_non_empty(value["initial_state"]["state_id"], "initial_state.state_id")
    _require_non_empty(value["initial_state"]["state_type"], "initial_state.state_type")
    _require_object(value["goal"], "goal")
    _require_fields(value["goal"], ("kind", "target"), "goal")
    _require_non_empty(value["goal"]["kind"], "goal.kind")
    _require_non_empty(value["goal"]["target"], "goal.target")

    transitions = value["transitions"]
    if not isinstance(transitions, list):
        raise ConformanceError("transitions must be an array")
    transition_ids: set[str] = set()
    for index, transition in enumerate(transitions):
        field = f"transitions[{index}]"
        _require_object(transition, field)
        _require_fields(
            transition,
            ("transition_id", "source", "relation", "target", "expected_cost"),
            field,
        )
        for name in ("transition_id", "source", "relation", "target"):
            _require_non_empty(transition[name], f"{field}.{name}")
        transition_id = transition["transition_id"]
        if transition_id in transition_ids:
            raise ConformanceError(f"duplicate transition_id: {transition_id}")
        transition_ids.add(transition_id)
        cost = transition["expected_cost"]
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0:
            raise ConformanceError(f"{field}.expected_cost must be non-negative")

    execution_policy = value["execution_policy"]
    _require_object(execution_policy, "execution_policy")
    _require_fields(
        execution_policy,
        ("max_steps", "rollback_on_failure", "constraint_mode"),
        "execution_policy",
    )
    max_steps = execution_policy["max_steps"]
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ConformanceError("execution_policy.max_steps must be a positive integer")

    trace_policy = value["trace_policy"]
    _require_object(trace_policy, "trace_policy")
    _require_fields(
        trace_policy,
        ("level", "include_alternatives", "include_state_data"),
        "trace_policy",
    )


def normalize_reason_ir(value: Mapping[str, Any]) -> dict[str, Any]:
    validate_reason_ir(value)
    normalized = copy.deepcopy(dict(value))
    normalized.setdefault("context_refs", [])
    normalized.setdefault("constraints", [])
    normalized.setdefault("planner_policy", None)
    normalized.setdefault("metadata", {})
    return normalized


def execute_reason_ir(value: Mapping[str, Any]) -> dict[str, Any]:
    ir = normalize_reason_ir(value)
    current = copy.deepcopy(ir["initial_state"])
    applied: list[str] = []
    trace_events: list[dict[str, Any]] = []
    total_cost = 0.0
    violations = [
        constraint["constraint_id"]
        for constraint in ir["constraints"]
        if not _constraint_passes(
            constraint["expression"], ir["initial_state"]["data"]
        )
    ]

    if not violations:
        for transition in ir["transitions"]:
            if transition["source"] != current["state_id"]:
                continue
            current = {
                "state_id": transition["target"],
                "state_type": current["state_type"],
                "data": copy.deepcopy(
                    transition.get("effect", {"identity": transition["target"]})
                ),
            }
            applied.append(transition["transition_id"])
            total_cost += transition["expected_cost"]
            trace_events.append(
                {
                    "event_type": "state_delta_applied",
                    "delta_id": f"delta-{len(applied)}",
                    "transition_id": transition["transition_id"],
                }
            )
            if len(applied) >= ir["execution_policy"]["max_steps"]:
                break

    status = (
        "rejected"
        if violations
        else "completed"
        if current["state_id"] == ir["goal"]["target"]
        else "failed"
    )

    return {
        "status": status,
        "final_state_id": current["state_id"],
        "applied_transition_ids": applied,
        "state_delta_count": len(applied),
        "trace_delta_ids": [
            event["delta_id"]
            for event in trace_events
            if event["event_type"] == "state_delta_applied"
        ],
        "expected_cost": total_cost,
        "violation_ids": violations,
    }


def execute_transaction_fixture(value: Mapping[str, Any]) -> dict[str, Any]:
    current = value["initial_state"]
    deltas: list[dict[str, Any]] = []
    records: list[str] = []
    candidates: dict[str, dict[str, Any]] = {}

    for operation in value["operations"]:
        kind = operation["op"]
        if kind == "prepare":
            candidate = operation["candidate_id"]
            if operation["source"] != current:
                raise ConformanceError("prepare source does not match current state")
            candidates[candidate] = dict(operation)
            records.append("prepared")
        elif kind == "validate":
            candidate = candidates[operation["candidate_id"]]
            candidate["accepted"] = bool(operation["accepted"])
            records.append("accepted" if candidate["accepted"] else "rejected")
        elif kind == "commit":
            candidate = candidates[operation["candidate_id"]]
            if not candidate.get("accepted"):
                raise ConformanceError("commit requires an accepted candidate")
            delta = {
                "delta_id": f"delta-{len(deltas) + 1}",
                "before": current,
                "after": candidate["target"],
                "transition_id": candidate["transition_id"],
            }
            current = candidate["target"]
            deltas.append(delta)
            records.append("committed")
        elif kind == "rollback":
            source = next(
                item for item in deltas if item["delta_id"] == operation["source_delta_id"]
            )
            delta = {
                "delta_id": f"delta-{len(deltas) + 1}",
                "before": current,
                "after": source["before"],
                "transition_id": f"rollback:{source['transition_id']}",
            }
            current = source["before"]
            deltas.append(delta)
            records.append("rolled_back")
        else:
            raise ConformanceError(f"unknown transaction operation: {kind}")

    return {
        "final_state_id": current,
        "delta_count": len(deltas),
        "record_statuses": records,
        "trace_delta_ids": [item["delta_id"] for item in deltas],
    }


@dataclass(frozen=True)
class Certification:
    sdk: str
    level: int
    label: str
    evidence: tuple[str, ...]


def certification_for(sdk: str, layers: Mapping[int, bool]) -> Certification:
    level = -1
    for candidate in range(5):
        if all(layers.get(required, False) for required in range(candidate + 1)):
            level = candidate
        else:
            break
    labels = {
        -1: "Not Certified",
        0: "Schema Compatible",
        1: "ReasonScript SDK Level 1 Certified",
        2: "ReasonScript SDK Level 2 Certified",
        3: "ReasonScript SDK Level 3 Certified",
        4: "ReasonScript SDK Full Compatible",
    }
    evidence = tuple(f"layer-{index}" for index in range(level + 1))
    return Certification(sdk, level, labels[level], evidence)


def _constraint_passes(expression: str, data: Any) -> bool:
    if not isinstance(data, Mapping):
        return True
    parts = expression.split()
    if len(parts) != 3 or parts[1] not in {">=", ">", "==", "<=", "<"}:
        return True
    field, operator, raw_expected = parts
    if field not in data:
        return True
    try:
        expected = float(raw_expected)
        actual = float(data[field])
    except (TypeError, ValueError):
        return True
    return {
        ">=": actual >= expected,
        ">": actual > expected,
        "==": actual == expected,
        "<=": actual <= expected,
        "<": actual < expected,
    }[operator]


def _require_object(value: Any, field: str) -> None:
    if not isinstance(value, Mapping):
        raise ConformanceError(f"{field} must be an object")


def _require_fields(value: Mapping[str, Any], names: tuple[str, ...], field: str) -> None:
    for name in names:
        if name not in value:
            raise ConformanceError(f"missing required field: {field}.{name}")


def _require_non_empty(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConformanceError(f"{field} must be a non-empty string")
