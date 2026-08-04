"""ReasonScript Visualization Standard Library v0.1 (`visual.*`)."""
from .artifacts import render_artifacts, render_titanic_artifacts
from .backend import VisualizationBackend
from .evaluation import (
    ClassificationEvaluation,
    ClassMetric,
    ConfusionMatrix,
    ConfusionMatrixCell,
    DecisionPathEvaluation,
    ErrorGroupEvaluation,
    EvaluationError,
    EvaluationVisualizationResult,
    EvaluationVisualizationSpec,
    PrecisionRecallCurve,
    PredictionEvidence,
    PredictionRecord,
    RocCurve,
    RuleEvaluation,
    ScoreDistribution,
    ThresholdPoint,
    classification_metrics,
    confidence_distribution,
    confusion_matrix,
    decision_path_frequency,
    error_distribution,
    evaluate_classification,
    evaluation_ir,
    evaluation_render_plan,
    normalized_confusion_matrix,
    precision_recall_curve,
    render_evaluation,
    roc_curve,
    rule_accuracy,
    rule_coverage,
    score_distribution,
)
from .matplotlib_backend import MatplotlibBackend
from .model import (
    AxisSpec,
    ChartSpec,
    EncodingSpec,
    LayoutSpec,
    LegendSpec,
    RenderSpec,
    SeriesSpec,
    TitleSpec,
    VisualizationArtifact,
    VisualizationDiagnostic,
    VisualizationError,
    VisualizationEvidence,
    VisualizationSpec,
)
from .operations import (
    add_series,
    area,
    bar,
    bar_horizontal,
    box,
    correlation,
    create,
    distribution,
    error_bar,
    from_table,
    grouped,
    heatmap,
    histogram,
    line,
    missingness,
    pie,
    scatter,
    set_layout,
    set_legend,
    set_render,
    set_title,
    set_x_axis,
    set_y_axis,
    stacked,
    titanic_charts,
)
from .provenance import evidence, explain, provenance
from .serialization import canonical_json, export_spec
from .validation import validate


def render(spec, table, output_dir, *, project_root=".", backend=None):
    return render_artifacts(spec, table, output_dir, project_root=project_root, backend=backend)
def render_png(spec, table, output_dir, **kwargs):
    from dataclasses import replace
    return render(replace(spec, render=replace(spec.render, formats=("png",))), table, output_dir, **kwargs)
def render_svg(spec, table, output_dir, **kwargs):
    from dataclasses import replace
    return render(replace(spec, render=replace(spec.render, formats=("svg",))), table, output_dir, **kwargs)
def aggregate(table, *, category, value, operation="mean", title="", **kwargs):
    return bar(table, category=category, value=value, aggregate=operation, title=title, **kwargs)

__all__ = [name for name in globals() if not name.startswith("_")]
