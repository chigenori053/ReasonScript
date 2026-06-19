"""runtime.prediction SDK module."""

from __future__ import annotations

from typing import Any

from frontend.runtime_integration import (
    RuntimeEngineRegistry,
    RuntimeValue,
    PredictionRequest,
)
from sdk._engine import resolve_registry
from sdk.types import SDKPredictionResult


def predict_state(
    state: str | Any,
    *,
    registry: RuntimeEngineRegistry | str | None = None,
) -> SDKPredictionResult | None:
    """Predict a state and return a typed SDKPredictionResult, or None on failure."""
    reg = resolve_registry(registry)
    if reg.prediction_engine is None:
        return None

    if isinstance(state, str):
        value = RuntimeValue.state(state)
    elif isinstance(state, RuntimeValue):
        value = state
    else:
        value = RuntimeValue.state(str(state))

    result = reg.prediction_engine.predict(PredictionRequest(value))
    if not result.value or result.diagnostics:
        return None

    fields = result.value.value.fields if hasattr(result.value.value, "fields") else {}
    return SDKPredictionResult(
        state=state if isinstance(state, str) else str(state),
        predicted=_bool_field(fields, "predicted", True),
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
