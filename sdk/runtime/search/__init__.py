"""runtime.search SDK module."""

from __future__ import annotations

from typing import Any

from frontend.runtime_integration import (
    RuntimeEngineRegistry,
    RuntimeValue,
    SearchRequest,
)
from sdk._engine import resolve_registry
from sdk.types import SDKSearchResult


def search_goal(
    goal: str | Any,
    *,
    registry: RuntimeEngineRegistry | str | None = None,
) -> SDKSearchResult | None:
    """Search for a goal and return a typed SDKSearchResult, or None on failure."""
    reg = resolve_registry(registry)
    if reg.search_engine is None:
        return None

    if isinstance(goal, str):
        value = RuntimeValue.goal(goal)
    elif isinstance(goal, RuntimeValue):
        value = goal
    else:
        value = RuntimeValue.goal(str(goal))

    result = reg.search_engine.search(SearchRequest(value))
    if not result.value or result.diagnostics:
        return None

    fields = result.value.value.fields if hasattr(result.value.value, "fields") else {}
    return SDKSearchResult(
        goal=goal if isinstance(goal, str) else str(goal),
        found=_bool_field(fields, "found", True),
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
