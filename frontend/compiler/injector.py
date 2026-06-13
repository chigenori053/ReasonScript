from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .errors import CompilerError, CompilerErrorCode


def _execution_default() -> dict[str, Any]:
    return {
        "max_steps": 128,
        "rollback_on_failure": True,
        "constraint_mode": "reject",
    }


def _trace_default() -> dict[str, Any]:
    return {
        "level": "standard",
        "include_alternatives": True,
        "include_state_data": True,
    }


def _planner_default() -> dict[str, Any]:
    return {
        "strategy": "minimum_expected_cost",
        "max_depth": 128,
        "max_alternatives": 8,
    }


@dataclass(frozen=True)
class CompilationPolicies:
    execution_policy: Mapping[str, Any] = field(default_factory=_execution_default)
    trace_policy: Mapping[str, Any] = field(default_factory=_trace_default)
    planner_policy: Mapping[str, Any] | None = field(default_factory=_planner_default)


@dataclass(frozen=True)
class CompilationContext:
    execution_policy: dict[str, Any]
    trace_policy: dict[str, Any]
    planner_policy: dict[str, Any] | None


def inject_policies(
    policies: CompilationPolicies | None = None,
) -> CompilationContext:
    selected = policies or CompilationPolicies()
    execution = dict(selected.execution_policy)
    trace = dict(selected.trace_policy)
    planner = (
        dict(selected.planner_policy)
        if selected.planner_policy is not None
        else None
    )
    _validate_execution(execution)
    _validate_trace(trace)
    if planner is not None:
        _validate_planner(planner)
    return CompilationContext(execution, trace, planner)


def _validate_execution(value: Mapping[str, Any]) -> None:
    _exact_keys(
        value,
        {"max_steps", "rollback_on_failure", "constraint_mode"},
        "execution_policy",
    )
    if (
        isinstance(value["max_steps"], bool)
        or not isinstance(value["max_steps"], int)
        or value["max_steps"] < 1
    ):
        _invalid("execution_policy.max_steps must be a positive integer")
    if not isinstance(value["rollback_on_failure"], bool):
        _invalid("execution_policy.rollback_on_failure must be boolean")
    _non_empty(value["constraint_mode"], "execution_policy.constraint_mode")


def _validate_trace(value: Mapping[str, Any]) -> None:
    _exact_keys(
        value,
        {"level", "include_alternatives", "include_state_data"},
        "trace_policy",
    )
    _non_empty(value["level"], "trace_policy.level")
    for key in ("include_alternatives", "include_state_data"):
        if not isinstance(value[key], bool):
            _invalid(f"trace_policy.{key} must be boolean")


def _validate_planner(value: Mapping[str, Any]) -> None:
    _exact_keys(
        value, {"strategy", "max_depth", "max_alternatives"}, "planner_policy"
    )
    _non_empty(value["strategy"], "planner_policy.strategy")
    for key in ("max_depth", "max_alternatives"):
        item = value[key]
        if item is not None and (
            isinstance(item, bool) or not isinstance(item, int) or item < 0
        ):
            _invalid(f"planner_policy.{key} must be a non-negative integer or null")


def _exact_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        _invalid(f"{name} fields must be exactly {sorted(expected)}")


def _non_empty(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _invalid(f"{name} must be a non-empty string")


def _invalid(message: str) -> None:
    raise CompilerError(CompilerErrorCode.INVALID_POLICY, None, message)
