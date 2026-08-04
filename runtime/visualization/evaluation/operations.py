"""Public evaluation-first visualization constructors."""
from __future__ import annotations
from dataclasses import asdict
from typing import Any, Sequence
from runtime.data import Table, is_missing
from ..model import EncodingSpec, RenderSpec, TitleSpec, VisualizationSpec
from .metrics import evaluate_classification
from .model import ClassificationEvaluation, EvaluationError, EvaluationVisualizationSpec


def _spec(table: Table, evaluation: ClassificationEvaluation, name: str, base_type: str, prepared: dict,
          title: str, normalization: str="none") -> EvaluationVisualizationSpec:
    visual=VisualizationSpec(base_type,{"table_ref":table.table_id,"dataset_ref":table.source_ref.dataset_id,
        "evaluation_ref":evaluation.evaluation_id,"prepared":prepared},EncodingSpec(),TitleSpec(title),render=RenderSpec(width=800,height=640))
    return EvaluationVisualizationSpec(evaluation.evaluation_id,name,visual,asdict(evaluation),normalization)


def confusion_matrix(table: Table, *, actual="actual", predicted="predicted", labels=None, title="Confusion Matrix", **kwargs):
    ev=evaluate_classification(table,actual=actual,predicted=predicted,labels=labels,**kwargs); matrix=ev.confusion_matrix
    return _spec(table,ev,"confusion_matrix","heatmap",{"x":list(matrix.labels),"y":list(matrix.labels),"matrix":[list(x) for x in matrix.matrix]},title)
def normalized_confusion_matrix(table: Table, *, actual="actual", predicted="predicted", labels=None, normalize="actual", title="Normalized Confusion Matrix", **kwargs):
    ev=evaluate_classification(table,actual=actual,predicted=predicted,labels=labels,**kwargs)
    if normalize not in ev.normalized_matrices: raise EvaluationError("MLV-MET-004","Invalid normalization")
    matrix=ev.normalized_matrices[normalize]
    return _spec(table,ev,"normalized_confusion_matrix","heatmap",{"x":list(matrix.labels),"y":list(matrix.labels),"matrix":[list(x) for x in matrix.matrix]},title,normalize)
def classification_metrics(table: Table, *, actual="actual", predicted="predicted", positive_label=None, title="Classification Metrics", **kwargs):
    ev=evaluate_classification(table,actual=actual,predicted=predicted,positive_label=positive_label,**kwargs)
    order=("accuracy","precision","recall","specificity","f1","balanced_accuracy"); values=[ev.metrics.get(x,0.0) for x in order]
    return _spec(table,ev,"classification_metrics","bar",{"series":[{"name":"metrics","x":list(order),"y":values}]},title)
def roc_curve(table: Table, *, actual="actual", score="prediction_score", positive_label=None, title="ROC Curve", **kwargs):
    ev=evaluate_classification(table,actual=actual,score=score,positive_label=positive_label,**kwargs); curve=ev.roc_curve
    prepared={"series":[{"name":f"ROC AUC={curve.auc:.4f}" if curve.auc is not None else "ROC","x":[p.false_positive_rate for p in curve.points],"y":[p.true_positive_rate for p in curve.points]}]}
    return _spec(table,ev,"roc_curve","line",prepared,title)
def precision_recall_curve(table: Table, *, actual="actual", score="prediction_score", positive_label=None, title="Precision–Recall Curve", **kwargs):
    ev=evaluate_classification(table,actual=actual,score=score,positive_label=positive_label,**kwargs); curve=ev.precision_recall_curve
    prepared={"series":[{"name":f"PR AP={curve.average_precision:.4f}" if curve.average_precision is not None else "PR","x":[p.recall for p in curve.points],"y":[p.precision for p in curve.points]}]}
    return _spec(table,ev,"precision_recall_curve","line",prepared,title)
def error_distribution(table: Table, *, actual="actual", predicted="predicted", group: str, positive_label=None, title="Error Distribution", **kwargs):
    ev=evaluate_classification(table,actual=actual,predicted=predicted,positive_label=positive_label,group_fields=(group,),**kwargs); items=ev.error_groups[group]
    prepared={"series":[{"name":"false_positive","x":[x.group_value for x in items],"y":[x.false_positive_count for x in items]},
                        {"name":"false_negative","x":[x.group_value for x in items],"y":[x.false_negative_count for x in items]}]}
    return _spec(table,ev,"error_distribution","grouped_bar",prepared,title)
def rule_coverage(table: Table, *, actual="actual", predicted="predicted", rule="rule_id", title="Rule Coverage", **kwargs):
    ev=evaluate_classification(table,actual=actual,predicted=predicted,rule=rule,**kwargs); items=ev.rules
    return _spec(table,ev,"rule_coverage","bar",{"series":[{"name":"coverage","x":[x.rule_id for x in items],"y":[x.coverage_ratio for x in items]}]},title)
def rule_accuracy(table: Table, *, actual="actual", predicted="predicted", rule="rule_id", title="Rule Accuracy", **kwargs):
    ev=evaluate_classification(table,actual=actual,predicted=predicted,rule=rule,**kwargs); items=ev.rules
    return _spec(table,ev,"rule_accuracy","bar",{"series":[{"name":"accuracy","x":[x.rule_id for x in items],"y":[x.accuracy for x in items]}]},title)
def decision_path_frequency(table: Table, *, actual="actual", predicted="predicted", path="decision_path", title="Decision Path Frequency", **kwargs):
    ev=evaluate_classification(table,actual=actual,predicted=predicted,path=path,**kwargs); items=ev.decision_paths
    return _spec(table,ev,"decision_path_frequency","bar_horizontal",{"series":[{"name":"frequency","x":[x.decision_path_id for x in items],"y":[x.execution_count for x in items]}]},title)


def _column_distribution(table:Table,column:str,group:str|None,name:str,title:str):
    if column not in table.column_names: raise EvaluationError("MLV-IN-004",f"Column not found: {column}")
    index=table.column_names.index(column); buckets={}
    for row in table.rows:
        value=row.values[index]
        if is_missing(value): continue
        if isinstance(value,bool) or not isinstance(value,(int,float)): raise EvaluationError("MLV-SCORE-002","Numeric value required")
        if not 0<=float(value)<=1: raise EvaluationError("MLV-SCORE-003","Value outside [0, 1]")
        if group in {None,"all"}: key="all"
        elif group=="correctness":
            if not {"actual","predicted"}<=set(table.column_names): raise EvaluationError("MLV-IN-002","Correctness grouping requires actual and predicted")
            key="correct" if row.values[table.column_names.index("actual")]==row.values[table.column_names.index("predicted")] else "incorrect"
        else:
            field={"actual_label":"actual","predicted_label":"predicted"}.get(group,group)
            if field not in table.column_names: raise EvaluationError("MLV-IN-002",f"Group column not found: {field}")
            raw=row.values[table.column_names.index(field)]; key="__MISSING__" if is_missing(raw) else raw
        buckets.setdefault(key,[]).append(float(value))
    prepared={"values":[v for values in buckets.values() for v in values],"groups":[{"name":str(k),"values":v} for k,v in sorted(buckets.items(),key=lambda x:(type(x[0]).__name__,str(x[0])))]}
    visual=VisualizationSpec("distribution",{"table_ref":table.table_id,"dataset_ref":table.source_ref.dataset_id,"prepared":prepared},EncodingSpec(),TitleSpec(title))
    return EvaluationVisualizationSpec("distribution_"+table.table_id,name,visual,prepared)
def confidence_distribution(table:Table,*,confidence="confidence",group="correctness",title="Confidence Distribution",**kwargs): return _column_distribution(table,confidence,group,"confidence_distribution",title)
def score_distribution(table:Table,*,score="prediction_score",group="actual",title="Score Distribution",**kwargs): return _column_distribution(table,score,group,"score_distribution",title)
