"""Reasoning Overview ViewModel builder for Phase 8D."""

from __future__ import annotations

import copy
import json
from typing import Any

CONTRACT_SCHEMA = "reasonscript-playground-reasoning-overview/1.0"
RUNTIME_SCHEMA = "reasonscript-reasoning-runtime-prototype/1.0"
MODEL_SCHEMA = "reasonscript-reasoning-model/1.0"
EVALUATION_SCHEMA = "reasonscript-reasoning-evaluation-report/1.0"

SEVERITY_ORDER = {"fatal": 0, "error": 1, "warning": 2, "info": 3}


def build_reasoning_overview_view_model(runtime_result: dict[str, Any] | None) -> dict[str, Any]:
    runtime = runtime_result if isinstance(runtime_result, dict) else {}
    model = _as_dict(runtime.get("reasoning_model"))
    report = _as_dict(runtime.get("evaluation_report"))
    diagnostics = _diagnostics(runtime, model, report)

    return _stable({
        "schemaVersion": CONTRACT_SCHEMA,
        "sourceRef": _source_ref(runtime),
        "runtimeStatus": _runtime_status(runtime, model, report, diagnostics),
        "modelSummary": _model_summary(model),
        "pipelineStatus": _pipeline_status(runtime),
        "inputState": _input_state(model),
        "reasoningPath": _reasoning_path(model),
        "knowledgeEmission": _knowledge_emission(model),
        "evaluationReport": _evaluation_report(report),
        "diagnostics": _diagnostics_summary(diagnostics),
        "rawArtifacts": {
            "runtimeResult": copy.deepcopy(runtime),
            "reasoningModel": copy.deepcopy(model),
            "evaluationReport": copy.deepcopy(report),
        },
    })


def serialize_reasoning_overview_view_model(view_model: dict[str, Any]) -> str:
    return json.dumps(_stable(view_model), ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def _source_ref(runtime: dict[str, Any]) -> dict[str, Any]:
    source_ref = _as_dict(runtime.get("source_ref"))
    return {
        "sourceId": str(source_ref.get("source_id") or "unavailable"),
        "sourceKind": str(source_ref.get("source_kind") or "unknown"),
        **({"sourcePath": str(source_ref["source_path"])} if source_ref.get("source_path") else {}),
    }


def _runtime_status(
    runtime: dict[str, Any],
    model: dict[str, Any],
    report: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    pipeline = _as_dict(runtime.get("pipeline_status"))
    fatal = [item for item in diagnostics if item["severity"] == "fatal"]
    return {
        "status": _runtime_status_value(pipeline.get("status")),
        "runId": str(runtime.get("run_id") or ""),
        "hasReasoningModel": bool(model),
        "hasEvaluationReport": bool(report),
        "diagnosticCount": len(diagnostics),
        "fatalDiagnosticCount": len(fatal),
    }


def _model_summary(model: dict[str, Any]) -> dict[str, Any]:
    input_state = _as_dict(model.get("input_state"))
    paths = _as_list(model.get("reasoning_paths"))
    steps = [step for path in paths if isinstance(path, dict) for step in _as_list(path.get("steps")) if isinstance(step, dict)]
    target = _as_dict(model.get("evaluation_target"))
    return {
        "available": bool(model),
        "modelId": str(model.get("model_id") or "ReasoningModel unavailable"),
        "modelSchemaVersion": str(model.get("schema_version") or ""),
        "selectedPathId": str(model.get("selected_path_id") or ""),
        "inputUnitCount": len(_as_list(input_state.get("units"))),
        "inputRelationCount": len(_as_list(input_state.get("relations"))),
        "reasoningPathCount": len(paths),
        "reasoningStepCount": len(steps),
        "knowledgeEmissionCount": len(_as_list(model.get("knowledge_emissions"))),
        "evaluationGoal": str(target.get("goal") or ""),
        "requiredChecks": [str(item) for item in _as_list(target.get("required_checks"))],
    }


def _pipeline_status(runtime: dict[str, Any]) -> dict[str, Any]:
    status = _as_dict(runtime.get("pipeline_status"))
    return {
        "status": _runtime_status_value(status.get("status")),
        "parserPassed": bool(status.get("parser_passed")),
        "reasonIrAvailable": bool(status.get("reason_ir_available")),
        "executionPlanAvailable": bool(status.get("execution_plan_available")),
        "simulationAvailable": bool(status.get("simulation_available")),
        "knowledgeAvailable": bool(status.get("knowledge_available")),
        "diagnosticsCount": int(status.get("diagnostics_count") or 0),
    }


def _input_state(model: dict[str, Any]) -> dict[str, Any]:
    input_state = _as_dict(model.get("input_state"))
    return {
        "inputId": str(input_state.get("input_id") or ""),
        "inputKind": str(input_state.get("input_kind") or ""),
        "units": [
            {
                "unitId": str(unit.get("unit_id") or ""),
                "unitType": str(unit.get("unit_type") or ""),
                "value": unit.get("value"),
            }
            for unit in _as_list(input_state.get("units"))
            if isinstance(unit, dict)
        ],
        "relations": [
            {
                "relationId": str(relation.get("relation_id") or ""),
                "relationType": str(relation.get("relation_type") or ""),
                "source": str(relation.get("source") or ""),
                "target": str(relation.get("target") or ""),
            }
            for relation in _as_list(input_state.get("relations"))
            if isinstance(relation, dict)
        ],
    }


def _reasoning_path(model: dict[str, Any]) -> dict[str, Any]:
    selected_path_id = str(model.get("selected_path_id") or "")
    paths = [_path_item(path) for path in _as_list(model.get("reasoning_paths")) if isinstance(path, dict)]
    selected = next((path for path in paths if path["pathId"] == selected_path_id), {})
    return {
        "selectedPathId": selected_path_id,
        "selectedPathSignature": str(selected.get("pathSignature") or ""),
        "paths": paths,
    }


def _path_item(path: dict[str, Any]) -> dict[str, Any]:
    return {
        "pathId": str(path.get("path_id") or ""),
        "pathSignature": str(path.get("path_signature") or ""),
        "status": _path_status(path.get("status")),
        "steps": [
            {
                "stepId": str(step.get("step_id") or ""),
                "stepType": str(step.get("step_type") or ""),
                "source": str(step.get("source") or ""),
                "operation": str(step.get("operation") or ""),
                "target": str(step.get("target") or ""),
                "evidenceRefs": [str(ref) for ref in _as_list(step.get("evidence_refs"))],
            }
            for step in _as_list(path.get("steps"))
            if isinstance(step, dict)
        ],
    }


def _knowledge_emission(model: dict[str, Any]) -> dict[str, Any]:
    emissions = []
    for item in _as_list(model.get("knowledge_emissions")):
        if not isinstance(item, dict):
            continue
        emissions.append({
            "knowledgeId": str(item.get("knowledge_id") or ""),
            "sourceStepId": str(item.get("source_step_id") or ""),
            "relation": str(item.get("relation") or ""),
            "source": str(item.get("source") or ""),
            "target": str(item.get("target") or ""),
            "evidencePath": [str(ref) for ref in _as_list(item.get("evidence_path"))],
            "pathSignature": str(item.get("path_signature") or ""),
        })
    return {"emissions": emissions}


def _evaluation_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = _as_dict(report.get("summary"))
    return {
        "available": bool(report),
        "reportId": str(report.get("report_id") or "EvaluationReport unavailable"),
        "status": _eval_status(summary.get("status")),
        "passed": bool(summary.get("passed")),
        "requiredChecksPassed": bool(summary.get("required_checks_passed")),
        "totalChecks": int(summary.get("total_checks") or 0),
        "passedChecks": int(summary.get("passed_checks") or 0),
        "failedChecks": int(summary.get("failed_checks") or 0),
        "warningChecks": int(summary.get("warning_checks") or 0),
        "fatalDiagnostics": int(summary.get("fatal_diagnostics") or 0),
        "checks": [
            {
                "checkId": str(check.get("check_id") or ""),
                "checkType": str(check.get("check_type") or ""),
                "required": bool(check.get("required")),
                "status": _check_status(check.get("status")),
                "passed": bool(check.get("passed")),
                "message": str(check.get("message") or ""),
                "evidenceRefs": [str(ref) for ref in _as_list(check.get("evidence_refs"))],
                "details": _as_dict(check.get("details")),
            }
            for check in _as_list(report.get("checks"))
            if isinstance(check, dict)
        ],
    }


def _diagnostics(runtime: dict[str, Any], model: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    items = (
        _diagnostic_items("runtime", runtime.get("diagnostics"))
        + _diagnostic_items("reasoning_model", model.get("diagnostics"))
        + _diagnostic_items("evaluation_report", report.get("diagnostics"))
    )
    if runtime and runtime.get("schema_version") != RUNTIME_SCHEMA:
        items.append(_diag("runtime", "RO-ART-001", "error", "Unsupported ReasoningRuntimeResult schema version.", "schema_version"))
    if model and model.get("schema_version") != MODEL_SCHEMA:
        items.append(_diag("reasoning_model", "RO-ART-002", "error", "Unsupported ReasoningModel schema version.", "schema_version"))
    if report and report.get("schema_version") != EVALUATION_SCHEMA:
        items.append(_diag("evaluation_report", "RO-ART-003", "error", "Unsupported ReasoningEvaluationReport schema version.", "schema_version"))
    return sorted(items, key=lambda item: (SEVERITY_ORDER[item["severity"]], item["source"], item["code"], item.get("location", ""), item["message"]))


def _diagnostics_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(items),
        "fatal": sum(1 for item in items if item["severity"] == "fatal"),
        "error": sum(1 for item in items if item["severity"] == "error"),
        "warning": sum(1 for item in items if item["severity"] == "warning"),
        "info": sum(1 for item in items if item["severity"] == "info"),
        "items": items,
    }


def _diagnostic_items(source: str, value: Any) -> list[dict[str, Any]]:
    result = []
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        result.append(_diag(
            source,
            str(item.get("code") or "RO-DIAG-UNKNOWN"),
            _severity(item.get("severity")),
            str(item.get("message") or ""),
            str(item["location"]) if item.get("location") is not None else None,
        ))
    return result


def _diag(source: str, code: str, severity: str, message: str, location: str | None) -> dict[str, Any]:
    value = {"source": source, "code": code, "severity": severity, "message": message}
    if location:
        value["location"] = location
    return value


def _runtime_status_value(value: Any) -> str:
    return str(value) if value in {"passed", "failed", "partial", "fatal"} else "unknown"


def _path_status(value: Any) -> str:
    return str(value) if value in {"selected", "candidate", "rejected", "failed"} else "unknown"


def _eval_status(value: Any) -> str:
    return str(value) if value in {"passed", "failed", "warning", "fatal"} else "unknown"


def _check_status(value: Any) -> str:
    return str(value) if value in {"passed", "failed", "warning", "skipped", "fatal"} else "unknown"


def _severity(value: Any) -> str:
    text = str(value or "info").lower()
    return text if text in SEVERITY_ORDER else "info"


def _stable(value: Any) -> Any:
    if isinstance(value, list):
        return [_stable(item) for item in value]
    if isinstance(value, dict):
        return {key: _stable(value[key]) for key in sorted(value)}
    return value


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
