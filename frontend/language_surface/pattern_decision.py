"""PatternDecisionIR builder for semantic pattern evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping

from .pattern_evaluator import PatternMatchResult


@dataclass(frozen=True)
class PatternDecisionIR:
    pattern_kind: str
    matched: bool
    matched_pattern: str | None
    matched_fields: tuple[str, ...]
    branch_id: str | None
    evaluation_trace: tuple[str, ...]
    confidence: float
    source_span: str | None = None


class PatternDecisionBuilder:
    def build(
        self,
        result: PatternMatchResult,
        *,
        pattern_kind: str = "StructPattern",
        matched_pattern: str | None = None,
        branch_id: str | None = None,
        source_span: str | None = None,
    ) -> PatternDecisionIR:
        return PatternDecisionIR(
            pattern_kind=pattern_kind,
            matched=result.matched,
            matched_pattern=matched_pattern,
            matched_fields=tuple(result.matched_fields),
            branch_id=branch_id,
            evaluation_trace=tuple(result.evaluation_trace),
            confidence=1.0 if result.matched else 0.0,
            source_span=source_span,
        )


def pattern_decision_to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            field.name: pattern_decision_to_json(getattr(value, field.name))
            for field in fields(value)
            if not (field.name == "source_span" and getattr(value, field.name) is None)
        }
        if isinstance(value, PatternDecisionIR):
            result["node_type"] = "PatternDecisionIRNode"
        else:
            result["node_type"] = type(value).__name__
        return result
    if isinstance(value, Mapping):
        return {str(key): pattern_decision_to_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [pattern_decision_to_json(item) for item in value]
    return value


def pattern_decision_from_json(value: Mapping[str, Any]) -> PatternDecisionIR:
    if value.get("node_type") not in {"PatternDecisionIR", "PatternDecisionIRNode"}:
        raise ValueError("document must contain PatternDecisionIRNode")
    return PatternDecisionIR(
        pattern_kind=str(value["pattern_kind"]),
        matched=bool(value["matched"]),
        matched_pattern=value.get("matched_pattern"),
        matched_fields=tuple(value.get("matched_fields", ())),
        branch_id=value.get("branch_id"),
        evaluation_trace=tuple(value.get("evaluation_trace", ())),
        confidence=float(value.get("confidence", 0.0)),
        source_span=value.get("source_span"),
    )
