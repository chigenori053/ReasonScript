"""Reference implementation of the frozen deterministic reasoning ABI."""

from __future__ import annotations

import json
import re
from typing import Any


PROFILE = "reasonscript-reasoning-core/1.0"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ReasoningReferenceError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def call_reasoning(function_id: str, argument: Any, *, backend: str = "RuntimeReal") -> tuple[dict[str, Any], dict[str, Any]]:
    operation = function_id.removeprefix("runtime.")
    if operation not in {"search", "simulate", "predict", "plan"}:
        raise ReasoningReferenceError("RI-1", f"unknown Runtime operation: {function_id}")
    label = _request_label(argument)
    execution_plan = _execution_plan(operation, label) if operation in {"search", "plan"} else None
    if operation == "search":
        inner = {"goal": label, "found": True, "cost": 1.0, "confidence": 1.0, "trace": ["search"]}
        engine = f"{backend} SearchEngine"
    elif operation == "simulate":
        inner = {"success": True, "final_state": label, "confidence": 1.0, "trace": ["simulate"]}
        engine = f"{backend} SemanticSimulationEngine"
    elif operation == "predict":
        inner = {"predicted_state": label, "confidence": 1.0, "evidence": ["predict"]}
        engine = f"{backend} PredictionEngine"
    else:
        inner = {"goal": label, "success": True, "cost": 1.0, "steps": ["step-1"]}
        engine = f"{backend} PlanningEngine"
    return {"some": inner}, {
        "operation": function_id,
        "backend": backend,
        "engine": engine,
        "trace": [f"{operation}:start", f"{operation}:complete"],
        "execution_plan": execution_plan,
        "native_profile": PROFILE,
    }


def _request_label(argument: Any) -> str:
    if isinstance(argument, str) and _IDENTIFIER.fullmatch(argument):
        return argument
    if isinstance(argument, dict):
        if isinstance(argument.get("name"), str):
            return argument["name"]
        return json.dumps(argument, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    raise ReasoningReferenceError(
        "ReasoningTypeConversionFailed", "argument cannot map to reasoning request"
    )


def _execution_plan(operation: str, target: str) -> dict[str, Any]:
    return {
        "schema_version": "execution-plan/0.1",
        "selected_steps": [{
            "step_id": f"{operation}-step-1",
            "transition_id": f"{operation}-transition",
            "source": "runtime",
            "target": target,
        }],
        "alternative_paths": [],
        "expected_cost": 1.0,
        "evidence_refs": [f"{operation}:trace"],
        "planner_version": "runtime-integration/0.2",
    }
