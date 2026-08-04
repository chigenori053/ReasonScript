"""Deterministic classification evaluation independent of rendering backends."""
from __future__ import annotations
from dataclasses import asdict
import json
import math
import statistics
from typing import Any, Iterable, Mapping, Sequence
from runtime.data import Table, is_missing, stable_id
from .model import (ClassificationEvaluation, ClassificationMetric, ClassMetric, ConfusionMatrix,
    DecisionPathEvaluation, ErrorGroupEvaluation, EvaluationError, PrecisionRecallCurve, PredictionEvidence,
    PredictionRecord, RocCurve, RuleEvaluation, ScoreDistribution, ThresholdPoint)


def evaluate_classification(table: Table, *, actual: str = "actual", predicted: str = "predicted",
                            score: str | None = "prediction_score", confidence: str | None = "confidence",
                            rule: str | None = "rule_id", path: str | None = "decision_path",
                            labels: Sequence[Any] | None = None, positive_label: Any | None = None,
                            group_fields: Sequence[str] = (), zero_division: float = 0.0) -> ClassificationEvaluation:
    if table.row_count == 0: raise EvaluationError("MLV-MET-001", "Empty evaluation dataset")
    if table.row_count > 1_000_000: raise EvaluationError("MLV-RES-001", "Too many prediction records")
    names = table.column_names
    for name, code in ((actual,"MLV-IN-002"),(predicted,"MLV-IN-003")):
        if name not in names: raise EvaluationError(code, f"Column not found: {name}")
    optional = {key: value if value in names else None for key, value in {"score":score,"confidence":confidence,"rule":rule,"path":path}.items()}
    for group in group_fields:
        if group not in names: raise EvaluationError("MLV-IN-002", f"Group column not found: {group}")
    records = _records(table, actual, predicted, optional, group_fields)
    resolved = tuple(labels) if labels is not None else tuple(sorted({r.actual for r in records}|{r.predicted for r in records}, key=_sort))
    if len(resolved) != len(set(resolved)): raise EvaluationError("MLV-LBL-005", "Duplicate label")
    if len(resolved) > 1000: raise EvaluationError("MLV-RES-002", "Too many classes")
    if any(r.actual not in resolved for r in records): raise EvaluationError("MLV-LBL-001", "Actual label is invalid")
    if any(r.predicted not in resolved for r in records): raise EvaluationError("MLV-LBL-002", "Predicted label is invalid")
    positive = positive_label if positive_label is not None else (resolved[-1] if len(resolved) == 2 else None)
    if positive is not None and positive not in resolved: raise EvaluationError("MLV-LBL-004", "Positive label not found")
    matrix = confusion(records, resolved)
    normalized = {kind: confusion(records, resolved, kind) for kind in ("actual","predicted","all")}
    metric_values = classification_metrics(matrix, positive, zero_division)
    metric_evidence = _metric_evidence(metric_values, matrix, positive, zero_division)
    roc, pr = curves(records, positive)
    rules = rule_evaluations(records, positive) if optional["rule"] else ()
    paths = path_evaluations(records) if optional["path"] else ()
    errors = {group: error_distribution(records, group, positive) for group in group_fields}
    distributions = {}
    if optional["score"]:
        for group in ("actual_label","predicted_label","correctness","rule_id","decision_path_id"):
            distributions[group] = score_distribution(records, group)
    eid = stable_id("eval", table.table_id, actual, predicted, optional, list(resolved), positive)
    col = {c.name:c.column_id for c in table.columns}
    evidence = PredictionEvidence(stable_id("eval_evidence",eid), eid, table.table_id, col[actual], col[predicted],
                                  col.get(optional["score"]), len(records), resolved, positive)
    return ClassificationEvaluation(eid, resolved, positive, len(records), matrix, normalized, metric_values,
                                    roc, pr, rules, paths, errors, distributions, metric_evidence, evidence)


def _records(table, actual, predicted, optional, groups):
    output=[]; names=table.column_names
    for row in table.rows:
        value=dict(zip(names,row.values)); a,p=value[actual],value[predicted]
        if is_missing(a): raise EvaluationError("MLV-LBL-001", "Actual label is missing")
        if is_missing(p): raise EvaluationError("MLV-LBL-002", "Predicted label is missing")
        score=_numeric(value.get(optional["score"]), "MLV-SCORE-002", "MLV-SCORE-003") if optional["score"] else None
        confidence=_numeric(value.get(optional["confidence"]), "MLV-SCORE-004", "MLV-SCORE-005") if optional["confidence"] else None
        raw_path=value.get(optional["path"]) if optional["path"] else None
        path_value=_path(raw_path) if raw_path is not None and not is_missing(raw_path) else ()
        group_values={g:("__MISSING__" if is_missing(value[g]) else value[g]) for g in groups}
        output.append(PredictionRecord(row.row_id,a,p,score,confidence,
            None if not optional["rule"] or is_missing(value.get(optional["rule"])) else str(value[optional["rule"]]),
            path_value,(),group_values))
    return tuple(output)


def _numeric(value, type_code, range_code):
    if value is None or is_missing(value): return None
    if isinstance(value,bool) or not isinstance(value,(int,float)): raise EvaluationError(type_code,"Numeric value required")
    result=float(value)
    if not math.isfinite(result) or not 0 <= result <= 1: raise EvaluationError(range_code,"Value outside [0, 1]")
    return result
def _path(value):
    if isinstance(value,(list,tuple)): items=value
    elif isinstance(value,str):
        try: parsed=json.loads(value); items=parsed if isinstance(parsed,list) else [value]
        except json.JSONDecodeError: items=[x.strip() for x in value.split(">")]
    else: raise EvaluationError("MLV-PATH-002","Invalid decision path")
    if not all(isinstance(x,str) for x in items): raise EvaluationError("MLV-PATH-002","Invalid decision path")
    return tuple(items)
def _sort(v): return (type(v).__name__,str(v))
def _ratio(n,d,z=0.0): return n/d if d else z


def confusion(records: Sequence[PredictionRecord], labels: Sequence[Any], normalize: str="none") -> ConfusionMatrix:
    if normalize not in {"none","actual","predicted","all"}: raise EvaluationError("MLV-MET-004","Invalid normalization")
    index={label:i for i,label in enumerate(labels)}; raw=[[0]*len(labels) for _ in labels]
    for r in records: raw[index[r.actual]][index[r.predicted]]+=1
    total=len(records); matrix=[]
    for i,row in enumerate(raw):
        values=[]
        for j,count in enumerate(row):
            denominator=1
            if normalize=="actual": denominator=sum(row)
            elif normalize=="predicted": denominator=sum(r[j] for r in raw)
            elif normalize=="all": denominator=total
            values.append(count if normalize=="none" else _ratio(count,denominator))
        matrix.append(tuple(values))
    correct=sum(raw[i][i] for i in range(len(labels)))
    return ConfusionMatrix(tuple(labels),tuple(matrix),total,correct,total-correct,normalize)


def classification_metrics(matrix: ConfusionMatrix, positive_label: Any|None, zero=0.0) -> dict[str,Any]:
    labels=matrix.labels; raw=matrix.matrix; total=matrix.total; per=[]
    for i,label in enumerate(labels):
        tp=int(raw[i][i]); fn=int(sum(raw[i])-tp); fp=int(sum(row[i] for row in raw)-tp); tn=total-tp-fn-fp
        precision=_ratio(tp,tp+fp,zero); recall=_ratio(tp,tp+fn,zero); specificity=_ratio(tn,tn+fp,zero); f1=_ratio(2*precision*recall,precision+recall,zero)
        per.append(ClassMetric(label,precision,recall,specificity,f1,tp+fn))
    accuracy=_ratio(matrix.correct,total,zero); macro={k:sum(getattr(x,k) for x in per)/len(per) for k in ("precision","recall","f1")}
    weighted={k:_ratio(sum(getattr(x,k)*x.support for x in per),total,zero) for k in ("precision","recall","f1")}
    micro={"precision":accuracy,"recall":accuracy,"f1":accuracy}; result={"overall_accuracy":accuracy,"accuracy":accuracy,
        "balanced_accuracy":macro["recall"],"per_class":[asdict(x) for x in per],"macro_average":macro,"micro_average":micro,"weighted_average":weighted}
    if positive_label is not None:
        item=per[labels.index(positive_label)]; i=labels.index(positive_label); tp=int(raw[i][i]); fn=int(sum(raw[i])-tp); fp=int(sum(r[i] for r in raw)-tp); tn=total-tp-fn-fp
        result.update({"precision":item.precision,"recall":item.recall,"specificity":item.specificity,"f1":item.f1,
            "true_positive":tp,"true_negative":tn,"false_positive":fp,"false_negative":fn,"support_positive":tp+fn,"support_negative":tn+fp})
    return result


def _metric_evidence(values, matrix, positive, zero):
    total=matrix.total; correct=matrix.correct; cells=("TP","TN","FP","FN")
    raw={"accuracy":(correct,total,("diagonal",)),"balanced_accuracy":(values["balanced_accuracy"],1,("per_class_recall",))}
    if positive is not None:
        tp,tn,fp,fn=(values[k] for k in ("true_positive","true_negative","false_positive","false_negative"))
        raw.update({"precision":(tp,tp+fp,("TP","FP")),"recall":(tp,tp+fn,("TP","FN")),
                    "specificity":(tn,tn+fp,("TN","FP")),"f1":(2*values["precision"]*values["recall"],values["precision"]+values["recall"],("precision","recall"))})
    return {name:ClassificationMetric(name,values[name],float(n),float(d),tuple(source),zero) for name,(n,d,source) in raw.items()}


def curves(records: Sequence[PredictionRecord], positive_label: Any|None) -> tuple[RocCurve,PrecisionRecallCurve]:
    diagnostic=({"code":"MLV-SCORE-001","severity":"warning","message":"Prediction score is unavailable"},)
    if positive_label is None or not any(r.prediction_score is not None for r in records):
        return RocCurve("skipped",positive_label,None,(),diagnostics=diagnostic), PrecisionRecallCurve("skipped",positive_label,None,(),diagnostics=diagnostic)
    scored=[r for r in records if r.prediction_score is not None]
    thresholds=sorted({r.prediction_score for r in scored},reverse=True)
    dropped=[r.record_id for r in records if r.prediction_score is None]; dropped_digest=stable_id("dropped_scores",dropped) if dropped else None
    if len(thresholds)<2:
        diagnostic=({"code":"MLV-SCORE-006","severity":"warning","message":"Insufficient score diversity"},)
        return (RocCurve("skipped",positive_label,None,(),len(dropped),dropped_digest,diagnostic),
                PrecisionRecallCurve("skipped",positive_label,None,(),len(dropped),dropped_digest,diagnostic))
    if len(thresholds)>100_000: raise EvaluationError("MLV-RES-003","Too many thresholds")
    points=[_threshold(scored,positive_label,None,"above_max",lambda _:False)]
    points.extend(_threshold(scored,positive_label,t,"value",lambda score,t=t:score>=t) for t in thresholds)
    points.append(_threshold(scored,positive_label,None,"below_min",lambda _:True))
    auc=sum((b.false_positive_rate-a.false_positive_rate)*(a.true_positive_rate+b.true_positive_rate)/2 for a,b in zip(points,points[1:]))
    ap=sum(max(0,b.recall-a.recall)*b.precision for a,b in zip(points,points[1:]))
    return (RocCurve("pass",positive_label,auc,tuple(points),len(dropped),dropped_digest),
            PrecisionRecallCurve("pass",positive_label,ap,tuple(points),len(dropped),dropped_digest))


def _threshold(records,positive,threshold,kind,predicate):
    included=[r for r in records if predicate(r.prediction_score)]; excluded=[r for r in records if not predicate(r.prediction_score)]
    tp=sum(r.actual==positive for r in included); fp=len(included)-tp
    fn=sum(r.actual==positive for r in excluded); tn=len(excluded)-fn
    return ThresholdPoint(threshold,kind,tp,tn,fp,fn,_ratio(tp,tp+fn),_ratio(fp,fp+tn),_ratio(tp,tp+fp),_ratio(tp,tp+fn),
        stable_id("included",[r.record_id for r in included]),stable_id("excluded",[r.record_id for r in excluded]))


def rule_evaluations(records: Sequence[PredictionRecord], positive_label: Any|None) -> tuple[RuleEvaluation,...]:
    buckets={}
    for r in records:
        if r.rule_id is None: raise EvaluationError("MLV-RULE-001","Rule ID is missing")
        buckets.setdefault(r.rule_id,[]).append(r)
    if len(buckets)>100_000: raise EvaluationError("MLV-RES-004","Too many rules")
    output=[]
    for rule,items in sorted(buckets.items()):
        correct=sum(r.actual==r.predicted for r in items); scores=[r.prediction_score for r in items if r.prediction_score is not None]; confidences=[r.confidence for r in items if r.confidence is not None]
        output.append(RuleEvaluation(rule,len(items),len(items)/len(records),correct,len(items)-correct,correct/len(items),
            sum(r.predicted==positive_label for r in items) if positive_label is not None else 0,
            sum(r.predicted!=positive_label for r in items) if positive_label is not None else 0,
            statistics.fmean(scores) if scores else None,statistics.fmean(confidences) if confidences else None,
            stable_id("records",[r.record_id for r in items])))
    return tuple(output)


def path_evaluations(records: Sequence[PredictionRecord]) -> tuple[DecisionPathEvaluation,...]:
    buckets={}
    for r in records:
        if not r.decision_path: raise EvaluationError("MLV-PATH-001","Decision path is missing")
        buckets.setdefault(r.decision_path,[]).append(r)
    if len(buckets)>100_000: raise EvaluationError("MLV-RES-005","Too many decision paths")
    output=[]
    for path,items in buckets.items():
        pid=stable_id("decision_path",list(path)); correct=sum(r.actual==r.predicted for r in items)
        scores=[r.prediction_score for r in items if r.prediction_score is not None]; confidences=[r.confidence for r in items if r.confidence is not None]
        output.append(DecisionPathEvaluation(pid,path,len(items),len(items)/len(records),correct,len(items)-correct,correct/len(items),
            statistics.fmean(scores) if scores else None,statistics.fmean(confidences) if confidences else None,
            tuple(sorted({r.rule_id for r in items if r.rule_id is not None})),stable_id("records",[r.record_id for r in items])))
    return tuple(sorted(output,key=lambda x:(-x.execution_count,x.decision_path_id)))


def error_distribution(records: Sequence[PredictionRecord], group: str, positive_label: Any|None) -> tuple[ErrorGroupEvaluation,...]:
    buckets={}
    for r in records: buckets.setdefault(r.groups.get(group,"__MISSING__"),[]).append(r)
    if len(buckets)>100_000: raise EvaluationError("MLV-RES-002","Too many group values")
    output=[]
    for value,items in sorted(buckets.items(),key=lambda x:_sort(x[0])):
        correct=sum(r.actual==r.predicted for r in items); fp=sum(r.actual!=positive_label and r.predicted==positive_label for r in items) if positive_label is not None else 0
        fn=sum(r.actual==positive_label and r.predicted!=positive_label for r in items) if positive_label is not None else 0
        output.append(ErrorGroupEvaluation(value,len(items),correct,len(items)-correct,fp,fn,(len(items)-correct)/len(items)))
    return tuple(output)


def score_distribution(records: Sequence[PredictionRecord], group: str) -> tuple[ScoreDistribution,...]:
    buckets={}
    for r in records:
        if r.prediction_score is None: continue
        key={"actual_label":r.actual,"predicted_label":r.predicted,"correctness":"correct" if r.actual==r.predicted else "incorrect",
             "rule_id":r.rule_id or "__MISSING__","decision_path_id":stable_id("decision_path",list(r.decision_path)) if r.decision_path else "__MISSING__"}[group]
        buckets.setdefault(key,[]).append(r.prediction_score)
    output=[]
    for key,values in sorted(buckets.items(),key=lambda x:_sort(x[0])):
        ordered=sorted(values); q=tuple(_quantile(ordered,p) for p in (.25,.5,.75)); bins=_bins(ordered)
        output.append(ScoreDistribution(key,len(ordered),ordered[0],ordered[-1],statistics.fmean(ordered),statistics.median(ordered),q,bins))
    return tuple(output)
def _quantile(values,p):
    if len(values)==1:return values[0]
    pos=(len(values)-1)*p; lo=int(pos); hi=min(lo+1,len(values)-1); return values[lo]+(values[hi]-values[lo])*(pos-lo)
def _bins(values,count=10):
    if not values:return ()
    low,high=min(values),max(values)
    if low==high:return ({"lower":low,"upper":high,"count":len(values)},)
    width=(high-low)/count; result=[]
    for i in range(count):
        lower=low+i*width; upper=high if i==count-1 else low+(i+1)*width
        result.append({"lower":lower,"upper":upper,"count":sum(lower<=v<upper or (i==count-1 and v==upper) for v in values)})
    return tuple(result)
