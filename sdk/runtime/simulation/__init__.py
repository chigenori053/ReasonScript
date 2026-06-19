"""runtime.simulation SDK module."""

from __future__ import annotations

from typing import Any

from frontend.runtime_integration import (
    RuntimeEngineRegistry,
    RuntimeValue,
    SimulationRequest,
)
from sdk._engine import resolve_registry
from sdk.types import SDKSimulationResult


def simulate_plan(
    plan: dict[str, Any] | str | Any,
    *,
    registry: RuntimeEngineRegistry | str | None = None,
) -> SDKSimulationResult | None:
    """Simulate an execution plan and return a typed SDKSimulationResult, or None on failure."""
    reg = resolve_registry(registry)
    if reg.simulation_engine is None:
        return None

    if isinstance(plan, dict):
        value = RuntimeValue.execution_plan(plan)
        plan_label = plan.get("name", "plan")
    elif isinstance(plan, RuntimeValue):
        value = plan
        plan_label = "plan"
    else:
        plan_label = str(plan)
        value = RuntimeValue.state(plan_label)

    result = reg.simulation_engine.simulate(SimulationRequest(value))
    if not result.value or result.diagnostics:
        return None

    fields = result.value.value.fields if hasattr(result.value.value, "fields") else {}
    return SDKSimulationResult(
        plan=plan_label,
        simulated=_bool_field(fields, "simulated", True),
        cost=_float_field(fields, "cost", 1.0),
        confidence=_float_field(fields, "confidence", 1.0),
        trace=result.trace,
        raw=result,
    )


def _bool_field(fields: dict, key: str, default: bool) -> bool:
    v = fields.get(key)
    return v.value if v and isinstance(v.value, bool) else default


def _float_field(fields: dict, key: str, default: float) -> float:
    v = fields.get(key)
    return float(v.value) if v and isinstance(v.value, (int, float)) else default
