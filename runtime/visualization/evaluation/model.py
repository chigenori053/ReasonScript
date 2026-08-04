"""Immutable JSON-safe models for ML evaluation visualization v0.2."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..model import VisualizationSpec


class EvaluationError(ValueError):
    def __init__(self, code: str, message: str, **details: Any):
        super().__init__(f"{code}: {message}"); self.code, self.message, self.details = code, message, details
    def diagnostic(self): return {"code": self.code, "severity": "error", "message": self.message, "details": self.details}


@dataclass(frozen=True)
class PredictionRecord:
    record_id: str; actual: Any; predicted: Any; prediction_score: float | None = None
    confidence: float | None = None; rule_id: str | None = None; decision_path: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = (); groups: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ConfusionMatrixCell:
    actual_label: Any; predicted_label: Any; count: int; value: float

@dataclass(frozen=True)
class ConfusionMatrix:
    labels: tuple[Any, ...]; matrix: tuple[tuple[float | int, ...], ...]; total: int; correct: int; incorrect: int
    normalization: str = "none"; schema_version: str = "reasonscript-confusion-matrix/0.2"

@dataclass(frozen=True)
class ClassificationMetric:
    name: str; result: float; numerator: float; denominator: float; source_cells: tuple[str, ...] = (); zero_division: float = 0.0

@dataclass(frozen=True)
class ClassMetric:
    label: Any; precision: float; recall: float; specificity: float; f1: float; support: int

@dataclass(frozen=True)
class ThresholdPoint:
    threshold: float | None; threshold_kind: str; true_positive: int; true_negative: int
    false_positive: int; false_negative: int; true_positive_rate: float; false_positive_rate: float
    precision: float; recall: float; included_digest: str; excluded_digest: str

@dataclass(frozen=True)
class RocCurve:
    status: str; positive_label: Any; auc: float | None; points: tuple[ThresholdPoint, ...]
    dropped_score_count: int = 0; dropped_score_digest: str | None = None
    diagnostics: tuple[Mapping[str, Any], ...] = (); schema_version: str = "reasonscript-roc-curve/0.2"

@dataclass(frozen=True)
class PrecisionRecallCurve:
    status: str; positive_label: Any; average_precision: float | None; points: tuple[ThresholdPoint, ...]
    dropped_score_count: int = 0; dropped_score_digest: str | None = None
    diagnostics: tuple[Mapping[str, Any], ...] = (); schema_version: str = "reasonscript-precision-recall-curve/0.2"

@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: str; applied_count: int; coverage_ratio: float; correct_count: int; incorrect_count: int
    accuracy: float; positive_predictions: int; negative_predictions: int; average_score: float | None
    average_confidence: float | None; matched_record_digest: str

@dataclass(frozen=True)
class DecisionPathEvaluation:
    decision_path_id: str; decision_path: tuple[str, ...]; execution_count: int; coverage_ratio: float
    correct_count: int; incorrect_count: int; accuracy: float; average_score: float | None
    average_confidence: float | None; rule_ids: tuple[str, ...]; matched_record_digest: str

@dataclass(frozen=True)
class ErrorGroupEvaluation:
    group_value: Any; total_count: int; correct_count: int; incorrect_count: int
    false_positive_count: int; false_negative_count: int; error_rate: float

@dataclass(frozen=True)
class ScoreDistribution:
    group_value: Any; count: int; minimum: float; maximum: float; mean: float; median: float
    quartiles: tuple[float, float, float]; bins: tuple[Mapping[str, Any], ...]

@dataclass(frozen=True)
class PredictionEvidence:
    evidence_id: str; evaluation_id: str; prediction_table_ref: str; actual_column_ref: str
    predicted_column_ref: str; score_column_ref: str | None; record_count: int; labels: tuple[Any, ...]
    positive_label: Any | None; operation: str = "classification_evaluation"

@dataclass(frozen=True)
class ClassificationEvaluation:
    evaluation_id: str; labels: tuple[Any, ...]; positive_label: Any | None; record_count: int
    confusion_matrix: ConfusionMatrix; normalized_matrices: Mapping[str, ConfusionMatrix]
    metrics: Mapping[str, Any]; roc_curve: RocCurve; precision_recall_curve: PrecisionRecallCurve
    rules: tuple[RuleEvaluation, ...]; decision_paths: tuple[DecisionPathEvaluation, ...]
    error_groups: Mapping[str, tuple[ErrorGroupEvaluation, ...]]; score_distributions: Mapping[str, tuple[ScoreDistribution, ...]]
    metric_evidence: Mapping[str, ClassificationMetric]; evidence: PredictionEvidence; diagnostics: tuple[Mapping[str, Any], ...] = ()
    schema_version: str = "reasonscript-classification-evaluation/0.2"

@dataclass(frozen=True)
class EvaluationVisualizationSpec:
    evaluation_ref: str; chart_type: str; visualization: VisualizationSpec; evaluation_data: Mapping[str, Any]
    normalization: str = "none"; schema_version: str = "reasonscript-evaluation-visualization-spec/0.2"
    @property
    def visualization_id(self): return self.visualization.visualization_id

@dataclass(frozen=True)
class EvaluationVisualizationResult:
    status: str; visualization_id: str; evaluation_ref: str; backend: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...]; evidence_refs: tuple[str, ...]; diagnostics: tuple[Mapping[str, Any], ...]
    schema_version: str = "reasonscript-evaluation-visualization-result/0.2"
