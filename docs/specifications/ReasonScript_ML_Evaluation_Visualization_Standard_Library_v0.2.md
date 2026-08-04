# ReasonScript ML Evaluation Visualization Standard Library v0.2

Status: VALIDATED

Specification ID: `reasonscript-ml-evaluation-visualization/0.2`

VSL v0.2 adds a renderer-independent classification evaluation layer under `runtime.visualization.evaluation`
and re-exports its public API through `visual.*`. Typed prediction Tables produce deterministic binary or
multiclass confusion matrices, normalized matrices, per-class and aggregate metrics, ROC/AUC, precision–recall/AP,
Rule coverage and accuracy, Decision Path analysis, error groups, score distributions, and traceable evidence.

Hard labels are never converted to pseudo-scores. When scores are absent, ROC, PR, and score image artifacts are
explicitly skipped with `MLV-SCORE-001`; matrix and metric evaluation remains available. Evaluation computation and
JSON artifacts do not import Matplotlib. Rendering uses the optional VSL v0.1 Matplotlib backend and retains project
root confinement, resource limits, canonical ordering, and same-environment artifact determinism.

Normative contracts are the `schemas/*evaluation*.schema.json`, `schemas/confusion_matrix.schema.json`,
`schemas/roc_curve.schema.json`, and `schemas/precision_recall_curve.schema.json` documents.
