import json
from dataclasses import asdict
from pathlib import Path
import pytest
from runtime import visual
from runtime.data import DataBackend, Field, Schema

SCHEMA=Schema((Field("actual","int"),Field("predicted","int"),Field("prediction_score","float",True),
 Field("confidence","float",True),Field("rule_id","string"),Field("decision_path","string"),Field("segment","string",True)))

@pytest.fixture
def table(tmp_path):
    rows=[
      {"actual":0,"predicted":0,"prediction_score":.1,"confidence":.9,"rule_id":"R-A","decision_path":"a>R-A","segment":"x"},
      {"actual":0,"predicted":1,"prediction_score":.7,"confidence":.7,"rule_id":"R-B","decision_path":"b>R-B","segment":"x"},
      {"actual":1,"predicted":0,"prediction_score":.4,"confidence":.6,"rule_id":"R-A","decision_path":"a>R-A","segment":"y"},
      {"actual":1,"predicted":1,"prediction_score":.9,"confidence":.9,"rule_id":"R-B","decision_path":"b>R-B","segment":None},]
    return DataBackend(project_root=tmp_path).from_external(rows,SCHEMA)

def test_binary_matrix_metrics_curves_rules_paths_and_json(table):
    ev=visual.evaluate_classification(table,positive_label=1,group_fields=("segment",))
    assert ev.confusion_matrix.matrix==((1,1),(1,1))
    assert ev.metrics["accuracy"]==.5 and ev.metrics["precision"]==.5 and ev.metrics["recall"]==.5
    assert ev.metrics["specificity"]==.5 and ev.metrics["f1"]==.5 and ev.metrics["balanced_accuracy"]==.5
    assert ev.roc_curve.status=="pass" and ev.roc_curve.auc==pytest.approx(.75)
    assert ev.precision_recall_curve.average_precision==pytest.approx(5/6)
    assert len(ev.rules)==2 and len(ev.decision_paths)==2 and len(ev.error_groups["segment"])==3
    json.dumps(asdict(ev),allow_nan=False)

def test_multiclass_normalization_and_averages(tmp_path):
    schema=Schema((Field("actual","string"),Field("predicted","string")))
    table=DataBackend(project_root=tmp_path).from_external([{"actual":"a","predicted":"a"},{"actual":"b","predicted":"c"},{"actual":"c","predicted":"c"}],schema)
    ev=visual.evaluate_classification(table,score=None,confidence=None,rule=None,path=None)
    assert ev.labels==("a","b","c") and ev.confusion_matrix.total==3
    assert ev.normalized_matrices["actual"].matrix[0][0]==1.0
    assert set(ev.metrics)>={"macro_average","micro_average","weighted_average","balanced_accuracy"}
    assert ev.roc_curve.status=="skipped" and ev.roc_curve.diagnostics[0]["code"]=="MLV-SCORE-001"

def test_public_specs_determinism_and_negative_contracts(table):
    specs=[visual.confusion_matrix(table,positive_label=1),visual.normalized_confusion_matrix(table,positive_label=1),
      visual.classification_metrics(table,positive_label=1),visual.roc_curve(table,positive_label=1),
      visual.precision_recall_curve(table,positive_label=1),visual.error_distribution(table,group="segment",positive_label=1),
      visual.rule_coverage(table,positive_label=1),visual.rule_accuracy(table,positive_label=1),
      visual.decision_path_frequency(table,positive_label=1),visual.confidence_distribution(table),visual.score_distribution(table)]
    for spec in specs:
        assert spec.visualization_id and json.dumps(asdict(spec),allow_nan=False)
    assert asdict(specs[0])==asdict(visual.confusion_matrix(table,positive_label=1))
    root=Path(__file__).parents[2]
    schema=json.loads((root/"schemas/classification_evaluation.schema.json").read_text())
    result=asdict(visual.evaluate_classification(table,positive_label=1))
    assert schema["properties"]["schema_version"]["const"]==result["schema_version"]
    assert set(schema["required"])<=set(result)
    with pytest.raises(visual.EvaluationError,match="MLV-IN-002"): visual.evaluate_classification(table,actual="missing")

def test_no_score_skipped_artifacts(tmp_path):
    schema=Schema((Field("actual","int"),Field("predicted","int")))
    table=DataBackend(project_root=tmp_path).from_external([{"actual":0,"predicted":0},{"actual":1,"predicted":1}],schema)
    spec=visual.roc_curve(table,score="prediction_score",positive_label=1,confidence=None,rule=None,path=None)
    result=visual.render_evaluation(spec,table,"out",project_root=tmp_path)
    assert result["status"]=="skipped" and result["diagnostics"][0]["code"]=="MLV-SCORE-001"
    manifest=json.loads((tmp_path/"out/evaluation_artifact_manifest.json").read_text())
    assert next(x for x in manifest["artifacts"] if x["name"]=="roc_curve.png")["status"]=="skipped"

def test_render_and_path_confinement(table,tmp_path):
    backend=visual.MatplotlibBackend(project_root=tmp_path); spec=visual.confusion_matrix(table,positive_label=1)
    if not backend.available(): pytest.skip("optional Matplotlib unavailable")
    first=visual.render_evaluation(spec,table,"eval1",project_root=tmp_path,backend=backend)
    second=visual.render_evaluation(spec,table,"eval2",project_root=tmp_path,backend=backend)
    h=lambda result:{x["name"]:x.get("sha256") for x in result["artifacts"] if x["name"].endswith((".png",".svg"))}
    assert first["status"]=="pass" and h(first)==h(second)
    with pytest.raises(visual.EvaluationError,match="MLV-ART-003"): visual.render_evaluation(spec,table,"../escape",project_root=tmp_path,backend=backend)
