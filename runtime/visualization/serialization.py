"""Canonical JSON projection for visualization values."""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import math
from pathlib import Path
from typing import Any
from .model import VisualizationError, VisualizationSpec


def to_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)): return value
    if isinstance(value, float):
        if not math.isfinite(value): raise VisualizationError("VSL-DET-002", "Non-canonical numeric value")
        return value
    if isinstance(value, Enum): return to_json_value(value.value)
    if isinstance(value, Path): return value.as_posix()
    if is_dataclass(value): return to_json_value(asdict(value))
    if isinstance(value, dict): return {str(k): to_json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [to_json_value(v) for v in value]
    raise VisualizationError("VSL-DET-002", f"Non-JSON visualization value: {type(value).__name__}")


def export_spec(spec: VisualizationSpec) -> dict[str, Any]: return to_json_value(spec)
def canonical_json(value: Any) -> str:
    return json.dumps(to_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
