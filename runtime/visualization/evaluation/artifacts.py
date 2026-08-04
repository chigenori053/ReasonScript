"""ML evaluation JSON and image artifact projection."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any
from runtime.data import Table
from ..artifacts import render_artifacts
from ..matplotlib_backend import MatplotlibBackend
from ..serialization import to_json_value
from .model import EvaluationVisualizationSpec


def evaluation_ir(spec: EvaluationVisualizationSpec) -> dict[str,Any]:
    mapping={"confusion_matrix":"ConfusionMatrixUnit","normalized_confusion_matrix":"ConfusionMatrixUnit",
        "classification_metrics":"MetricComputationUnit","roc_curve":"RocComputationUnit",
        "precision_recall_curve":"PrecisionRecallComputationUnit","rule_coverage":"RuleGroupingUnit",
        "rule_accuracy":"RuleGroupingUnit","decision_path_frequency":"DecisionPathGroupingUnit",
        "error_distribution":"ErrorGroupingUnit","score_distribution":"ScoreDistributionUnit",
        "confidence_distribution":"ScoreDistributionUnit"}
    return {"schema_version":"reasonscript-evaluation-visualization-ir/0.2","visualization_id":spec.visualization_id,
        "evaluation_ref":spec.evaluation_ref,"units":[{"unit_type":"PredictionBindingUnit"},{"unit_type":"LabelResolutionUnit"},
        {"unit_type":mapping[spec.chart_type]},{"unit_type":"EvaluationEncodingUnit"},{"unit_type":"EvaluationRenderUnit"},{"unit_type":"EvaluationArtifactUnit"}]}


def evaluation_render_plan(spec):
    steps=("resolve_prediction_table","validate_columns","resolve_labels","validate_values","resolve_positive_label",
        "validate_scores","compute_confusion_matrix","compute_metrics","generate_thresholds","compute_roc",
        "compute_precision_recall","aggregate_rules","aggregate_decision_paths","aggregate_errors","build_spec",
        "configure_axes","render_png","render_svg","compute_digests","emit_evidence","emit_validation","emit_manifest")
    score_status=spec.evaluation_data.get("roc_curve",{}).get("status")
    return {"schema_version":"reasonscript-evaluation-render-plan/0.2","evaluation_ref":spec.evaluation_ref,
        "steps":[{"ordinal":i,"operation":step,"status":"skipped" if score_status=="skipped" and step in {"generate_thresholds","compute_roc","compute_precision_recall"} else "planned"} for i,step in enumerate(steps)]}


def render_evaluation(spec: EvaluationVisualizationSpec, table: Table, output_dir: str|Path, *, project_root: str|Path=".", backend=None):
    renderer=backend or MatplotlibBackend(project_root=project_root); root=renderer.project_root
    target=(root/output_dir).resolve() if not Path(output_dir).is_absolute() else Path(output_dir).resolve()
    if target!=root and root not in target.parents:
        from .model import EvaluationError; raise EvaluationError("MLV-ART-003","Output path traversal rejected")
    target.mkdir(parents=True,exist_ok=True)
    score_key="roc_curve" if spec.chart_type=="roc_curve" else "precision_recall_curve" if spec.chart_type=="precision_recall_curve" else None
    skipped=score_key is not None and spec.evaluation_data.get(score_key,{}).get("status")=="skipped"
    base=None
    if not skipped:
        base=render_artifacts(spec.visualization,table,target,project_root=root,backend=renderer)
        for fmt in spec.visualization.render.formats: shutil.copyfile(target/f"chart.{fmt}",target/f"{spec.chart_type}.{fmt}")
    evaluation=spec.evaluation_data
    documents={"classification_evaluation.json":evaluation,
        "confusion_matrix.json":evaluation.get("confusion_matrix",{}),"classification_metrics.json":evaluation.get("metrics",{}),
        "roc_curve.json":evaluation.get("roc_curve",{}),"precision_recall_curve.json":evaluation.get("precision_recall_curve",{}),
        "rule_coverage.json":{"items":evaluation.get("rules",[])},"decision_path_frequency.json":{"items":evaluation.get("decision_paths",[])},
        "error_distribution.json":{"groups":evaluation.get("error_groups",{})},"score_distribution.json":{"groups":evaluation.get("score_distributions",{})},
        "prediction_evidence.json":evaluation.get("evidence",{}),
        "evaluation_validation.json":{"schema_version":"reasonscript-evaluation-validation/0.2","status":"pass","diagnostics":[]},
        "evaluation_visualization_spec.json":to_json_value(spec),"evaluation_visualization_ir.json":evaluation_ir(spec),
        "evaluation_render_plan.json":evaluation_render_plan(spec),
        "evaluation_visualization_evidence.json":{"schema_version":"reasonscript-evaluation-visualization-evidence/0.2","evaluation_ref":spec.evaluation_ref,"prediction_evidence_ref":evaluation.get("evidence",{}).get("evidence_id")}}
    for name,value in documents.items(): (target/name).write_text(json.dumps(to_json_value(value),ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    items=[{"name":name,"status":"generated","sha256":hashlib.sha256((target/name).read_bytes()).hexdigest()} for name in sorted(documents)]
    for fmt in spec.visualization.render.formats: items.append({"name":f"{spec.chart_type}.{fmt}","status":"skipped" if skipped else "generated",
        **({} if skipped else {"sha256":hashlib.sha256((target/f"{spec.chart_type}.{fmt}").read_bytes()).hexdigest()})})
    manifest={"schema_version":"reasonscript-evaluation-artifact-manifest/0.2","evaluation_ref":spec.evaluation_ref,"artifacts":items}
    (target/"evaluation_artifact_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"schema_version":"reasonscript-evaluation-visualization-result/0.2","status":"skipped" if skipped else "pass",
        "visualization_id":spec.visualization_id,"evaluation_ref":spec.evaluation_ref,
        "backend":None if skipped else base["backend"],"artifacts":items,"evidence_refs":[evaluation.get("evidence",{}).get("evidence_id")],
        "diagnostics":evaluation.get(score_key,{}).get("diagnostics",[]) if skipped else []}
