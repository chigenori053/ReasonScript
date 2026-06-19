"""Shared SDK result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SDKSearchResult:
    goal: str
    found: bool
    cost: float
    confidence: float
    trace: tuple[str, ...]
    raw: Any = None


@dataclass(frozen=True)
class SDKSimulationResult:
    plan: str
    simulated: bool
    cost: float
    confidence: float
    trace: tuple[str, ...]
    raw: Any = None


@dataclass(frozen=True)
class SDKPredictionResult:
    state: str
    predicted: bool
    cost: float
    confidence: float
    trace: tuple[str, ...]
    raw: Any = None


@dataclass(frozen=True)
class SDKPlanningResult:
    goal: str
    planned: bool
    cost: float
    confidence: float
    trace: tuple[str, ...]
    execution_plan: dict[str, Any] | None = None
    raw: Any = None
