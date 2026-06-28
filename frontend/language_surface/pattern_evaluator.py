"""Deterministic evaluator for semantic struct patterns."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping

from .semantic_patterns import (
    SemanticBindingPattern,
    SemanticDefaultPattern,
    SemanticLiteralPattern,
    SemanticPattern,
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
    children: tuple["PatternMatchResult", ...] = ()
    bindings: dict[str, Any] | None = None


class PatternEvaluator:
    def evaluate(
        self,
        pattern: SemanticStructPattern,
        value: RuntimeStructValue,
    ) -> PatternMatchResult:
        return self.evaluate_pattern(pattern, value)

    def evaluate_pattern(
        self,
        pattern: SemanticPattern,
        value: Any,
    ) -> PatternMatchResult:
        if isinstance(pattern, SemanticStructPattern):
            return self.evaluate_struct(pattern, value)
        if isinstance(pattern, SemanticLiteralPattern):
            return self.evaluate_literal(pattern, value)
        if isinstance(pattern, SemanticQualifiedPattern):
            return self.evaluate_qualified(pattern, value)
        if isinstance(pattern, SemanticWildcardPattern):
            return self.evaluate_wildcard(pattern, value)
        if isinstance(pattern, SemanticDefaultPattern):
            return self.evaluate_default(pattern, value)
        if isinstance(pattern, SemanticBindingPattern):
            return self.evaluate_binding(pattern, value)
        return PatternMatchResult(
            False,
            (),
            None,
            "UnsupportedPattern",
            (_value_label(value), "NotMatched"),
        )

    def evaluate_struct(
        self,
        pattern: SemanticStructPattern,
        value: Any,
    ) -> PatternMatchResult:
        trace: list[str] = [pattern.struct_symbol]
        if not isinstance(value, RuntimeStructValue):
            trace.append(_value_label(value))
            trace.append("NotMatched")
            return PatternMatchResult(
                False,
                (),
                None,
                "StructTypeMismatch",
                tuple(trace),
            )
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
        children: list[PatternMatchResult] = []
        bindings: dict[str, Any] = {}
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
                    tuple(children),
                )
            child = self.evaluate_pattern(field.pattern, runtime_value)
            children.append(child)
            if child.bindings:
                bindings.update(child.bindings)
            trace.extend(child.evaluation_trace)
            if not child.matched:
                return PatternMatchResult(
                    False,
                    tuple(matched_fields),
                    field.field_symbol,
                    child.failure_reason,
                    tuple(trace),
                    tuple(children),
                )
            matched_fields.append(field.field_symbol)

        trace.append("Matched")
        return PatternMatchResult(
            True,
            tuple(matched_fields),
            None,
            None,
            tuple(trace),
            tuple(children),
            bindings or None,
        )

    def evaluate_literal(
        self,
        pattern: SemanticLiteralPattern,
        value: Any,
    ) -> PatternMatchResult:
        matched = pattern.value == value
        return PatternMatchResult(
            matched,
            (),
            None,
            None if matched else "LiteralMismatch",
            (_value_label(value), "Matched" if matched else "NotMatched"),
        )

    def evaluate_qualified(
        self,
        pattern: SemanticQualifiedPattern,
        value: Any,
    ) -> PatternMatchResult:
        if not isinstance(value, RuntimeEnumValue):
            return PatternMatchResult(
                False,
                (),
                None,
                "EnumVariantMismatch",
                (_value_label(value), "NotMatched"),
            )
        matched = (
            pattern.namespace == value.enum_name
            and pattern.identifier == value.variant_name
        )
        return PatternMatchResult(
            matched,
            (),
            None,
            None if matched else "EnumVariantMismatch",
            (value.symbol, "Matched" if matched else "NotMatched"),
        )

    def evaluate_wildcard(
        self,
        pattern: SemanticWildcardPattern,
        value: Any,
    ) -> PatternMatchResult:
        return PatternMatchResult(
            True,
            (),
            None,
            None,
            (_value_label(value), "Matched"),
        )

    def evaluate_default(
        self,
        pattern: SemanticDefaultPattern,
        value: Any,
    ) -> PatternMatchResult:
        return PatternMatchResult(
            False,
            (),
            None,
            "DefaultPatternNotAllowed",
            (_value_label(value), "NotMatched"),
        )

    def evaluate_binding(
        self,
        pattern: SemanticBindingPattern,
        value: Any,
    ) -> PatternMatchResult:
        return PatternMatchResult(
            True,
            (),
            None,
            None,
            (_value_label(value), "Matched"),
            (),
            {pattern.binding: value},
        )


def pattern_match_result_to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            field.name: pattern_match_result_to_json(getattr(value, field.name))
            for field in fields(value)
            if not (isinstance(value, PatternMatchResult) and field.name == "bindings")
        }
        if isinstance(value, PatternMatchResult):
            result["matched_fields"] = list(value.matched_fields)
            result["evaluation_trace"] = list(value.evaluation_trace)
            result["children"] = [
                pattern_match_result_to_json(item) for item in value.children
            ]
            if value.bindings:
                result["bindings"] = pattern_match_result_to_json(value.bindings)
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
        tuple(
            pattern_match_result_from_json(item)
            for item in value.get("children", ())
        ),
        dict(value["bindings"]) if value.get("bindings") else None,
    )


def _value_label(value: Any) -> str:
    if isinstance(value, RuntimeEnumValue):
        return value.symbol
    if isinstance(value, RuntimeStructValue):
        return value.type_name
    return str(value)


_MISSING = object()
