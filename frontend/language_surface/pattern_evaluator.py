"""Deterministic evaluator for semantic struct patterns."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping

from .semantic_patterns import (
    SemanticDefaultPattern,
    SemanticLiteralPattern,
    SemanticQualifiedPattern,
    SemanticStructPattern,
    SemanticWildcardPattern,
)


@dataclass(frozen=True)
class RuntimeEnumValue:
    enum_name: str
    variant_name: str

    @property
    def symbol(self) -> str:
        return f"{self.enum_name}.{self.variant_name}"


@dataclass(frozen=True)
class RuntimeStructFieldValue:
    field_name: str
    value: Any


@dataclass(frozen=True)
class RuntimeStructValue:
    type_name: str
    fields: tuple[RuntimeStructFieldValue, ...]

    @staticmethod
    def from_mapping(type_name: str, fields: Mapping[str, Any]) -> "RuntimeStructValue":
        return RuntimeStructValue(
            type_name,
            tuple(RuntimeStructFieldValue(name, value) for name, value in fields.items()),
        )

    def field(self, name: str) -> Any:
        for field in self.fields:
            if field.field_name == name:
                return field.value
        return _MISSING


@dataclass(frozen=True)
class PatternMatchResult:
    matched: bool
    matched_fields: tuple[str, ...] = ()
    failed_field: str | None = None
    failure_reason: str | None = None
    evaluation_trace: tuple[str, ...] = ()


class PatternEvaluator:
    def evaluate(
        self,
        pattern: SemanticStructPattern,
        value: RuntimeStructValue,
    ) -> PatternMatchResult:
        trace: list[str] = [pattern.struct_symbol]
        if pattern.struct_symbol != value.type_name:
            trace.append(value.type_name)
            trace.append("NotMatched")
            return PatternMatchResult(
                False,
                (),
                None,
                "StructTypeMismatch",
                tuple(trace),
            )

        matched_fields: list[str] = []
        for field in pattern.fields:
            trace.append(field.field_symbol)
            runtime_value = value.field(field.field_symbol)
            if runtime_value is _MISSING:
                trace.append("MissingField")
                return PatternMatchResult(
                    False,
                    tuple(matched_fields),
                    field.field_symbol,
                    "MissingField",
                    tuple(trace),
                )
            matched, reason, value_label = _evaluate_field_pattern(
                field.pattern,
                runtime_value,
            )
            trace.append(value_label)
            trace.append("Matched" if matched else "NotMatched")
            if not matched:
                return PatternMatchResult(
                    False,
                    tuple(matched_fields),
                    field.field_symbol,
                    reason,
                    tuple(trace),
                )
            matched_fields.append(field.field_symbol)

        trace.append("Matched")
        return PatternMatchResult(True, tuple(matched_fields), None, None, tuple(trace))


def pattern_match_result_to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            field.name: pattern_match_result_to_json(getattr(value, field.name))
            for field in fields(value)
        }
        if isinstance(value, PatternMatchResult):
            result["matched_fields"] = list(value.matched_fields)
            result["evaluation_trace"] = list(value.evaluation_trace)
        result["node_type"] = type(value).__name__
        return result
    if isinstance(value, Mapping):
        return {str(key): pattern_match_result_to_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [pattern_match_result_to_json(item) for item in value]
    return value


def pattern_match_result_from_json(value: Mapping[str, Any]) -> PatternMatchResult:
    if value.get("node_type") != "PatternMatchResult":
        raise ValueError("document must contain PatternMatchResult")
    return PatternMatchResult(
        bool(value["matched"]),
        tuple(value.get("matched_fields", ())),
        value.get("failed_field"),
        value.get("failure_reason"),
        tuple(value.get("evaluation_trace", ())),
    )


def _evaluate_field_pattern(pattern: Any, value: Any) -> tuple[bool, str | None, str]:
    if isinstance(pattern, SemanticQualifiedPattern):
        if not isinstance(value, RuntimeEnumValue):
            return False, "EnumVariantMismatch", _value_label(value)
        return (
            pattern.namespace == value.enum_name and pattern.identifier == value.variant_name,
            None if pattern.namespace == value.enum_name and pattern.identifier == value.variant_name else "EnumVariantMismatch",
            value.symbol,
        )
    if isinstance(pattern, SemanticLiteralPattern):
        return (
            pattern.value == value,
            None if pattern.value == value else "LiteralMismatch",
            _value_label(value),
        )
    if isinstance(pattern, SemanticWildcardPattern):
        return True, None, _value_label(value)
    if isinstance(pattern, SemanticDefaultPattern):
        return False, "DefaultPatternNotAllowed", _value_label(value)
    return False, "UnsupportedPattern", _value_label(value)


def _value_label(value: Any) -> str:
    if isinstance(value, RuntimeEnumValue):
        return value.symbol
    if isinstance(value, RuntimeStructValue):
        return value.type_name
    return str(value)


_MISSING = object()
