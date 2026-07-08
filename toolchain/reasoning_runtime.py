"""Reasoning Runtime Prototype for reasonscript-reasoning-runtime-prototype/1.0.

Phase 8C projects existing ReasonScript pipeline artifacts into Phase 8A
ReasoningModel artifacts, evaluates them with the Phase 8B evaluator, and
bundles the result without changing parser or runtime semantics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.reason_cli import _analyze_result
from toolchain.reasoning_evaluation_report import (
    evaluate_reasoning_model as _evaluate_reasoning_model,
    serialize_evaluation_report,
    validate_evaluation_report,
)
from toolchain.reasoning_model_contract import (
    CONTRACT_SCHEMA as MODEL_SCHEMA,
    serialize_reasoning_model,
    validate as validate_reasoning_model,
)

CONTRACT_SCHEMA = "reasonscript-reasoning-runtime-prototype/1.0"
VALIDATOR_SCHEMA = "reasonscript-reasoning-runtime-prototype-validator/1.0"

SOURCE_KINDS = ("reason_script_source", "fixture", "inline_source", "pipeline_artifact_bundle")
PIPELINE_STATUSES = ("passed", "failed", "partial", "fatal")
SEVERITIES = ("info", "warning", "error", "fatal")
FAILING_SEVERITIES = ("error", "fatal")

TOP_LEVEL_ORDER = (
    "schema_version",
    "run_id",
    "source_ref",
    "pipeline_status",
    "reasoning_model",
    "evaluation_report",
    "diagnostics",
    "metadata",
)
SOURCE_REF_ORDER = ("source_id", "source_kind", "source_path", "artifact_refs")
PIPELINE_STATUS_ORDER = (
    "status",
    "parser_passed",
    "reason_ir_available",
    "execution_plan_available",
    "simulation_available",
    "knowledge_available",
    "diagnostics_count",
)
DIAGNOSTIC_ORDER = ("code", "severity", "message", "location")

REQUIRED_CHECKS = ["reachability", "determinism", "evidence_completeness", "consistency"]


def run_reasoning_runtime(source_or_artifacts: str | Path | dict[str, Any]) -> dict[str, Any]:
    bundle = _artifact_bundle(source_or_artifacts)
    source_ref = _source_ref(bundle)
    diagnostics = _pipeline_diagnostics(bundle)
    pipeline_status = _pipeline_status(bundle, diagnostics)

    model: dict[str, Any] = {}
    report: dict[str, Any] = {}
    if pipeline_status["status"] in {"passed", "partial"}:
        model = build_reasoning_model_from_artifacts(bundle)
        model_result = validate_reasoning_model(model)
        if not model_result["valid"]:
            diagnostics.append(_diag("RRP-PROJ-007", "Generated ReasoningModel failed validation", location="reasoning_model"))
        else:
            report = evaluate_generated_reasoning_model(model)
            report_result = validate_evaluation_report(report)
            if not report_result["valid"]:
                diagnostics.append(_diag("RRP-EVAL-002", "Generated ReasoningEvaluationReport failed validation", location="evaluation_report"))
            if isinstance(report.get("summary"), dict) and not report["summary"].get("passed", False):
                diagnostics.append(_diag("RRP-EVAL-003", "Required evaluation checks failed", severity="warning", location="evaluation_report.summary"))

    return _canonicalize({
        "schema_version": CONTRACT_SCHEMA,
        "run_id": f"run_{_slug(source_ref.get('source_id', 'runtime'))}",
        "source_ref": source_ref,
        "pipeline_status": pipeline_status,
        "reasoning_model": model,
        "evaluation_report": report,
        "diagnostics": _sort_diagnostics(diagnostics),
    })


def build_reasoning_model_from_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    source_ref = _source_ref(artifacts)
    payload = artifacts.get("artifacts") if isinstance(artifacts.get("artifacts"), dict) else artifacts
    reason_ir = _as_dict(payload.get("reason_ir"))
    execution_plan = _as_dict(payload.get("execution_plan"))
    simulation = _as_dict(payload.get("simulation"))
    knowledge = _as_dict(payload.get("knowledge"))

    source_id = source_ref["source_id"]
    module_name = _module_name(reason_ir, artifacts) or source_id
    units, relations = _input_units_and_relations(reason_ir, execution_plan, knowledge)
    steps = _reasoning_steps(execution_plan, reason_ir, simulation)
    path_signature = _path_signature(execution_plan, simulation, steps)
    selected_path_id = "path_main" if steps else ""
    emissions = _knowledge_emissions(knowledge, steps, path_signature)
    target = _evaluation_target(execution_plan, simulation, emissions, steps)
    diagnostics = []
    if not units:
        diagnostics.append(_diag("RRP-PROJ-002", "Failed to construct input_state", severity="warning", location="input_state"))
    if not steps:
        diagnostics.append(_diag("RRP-PROJ-003", "Failed to construct reasoning path", location="reasoning_paths"))
    if not selected_path_id:
        diagnostics.append(_diag("RRP-PROJ-004", "Failed to derive selected_path_id", location="selected_path_id"))

    return json.loads(serialize_reasoning_model({
        "schema_version": MODEL_SCHEMA,
        "model_id": f"{module_name}.ReasoningModel",
        "source_ref": {
            "source_id": source_id,
            "source_kind": source_ref["source_kind"],
            "artifact_refs": {
                "reason_ir": "reason_ir.json",
                "execution_plan": "execution_plan.json",
                "simulation": "simulation.json",
                "knowledge": "knowledge.json",
            },
        },
        "input_state": {
            "input_id": f"input_{_slug(source_id)}",
            "input_kind": "structured_state",
            "units": units,
            "relations": relations,
        },
        "reasoning_paths": [{
            "path_id": selected_path_id,
            "path_signature": path_signature,
            "status": "selected",
            "steps": steps,
        }] if steps else [],
        "selected_path_id": selected_path_id,
        "knowledge_emissions": emissions,
        "evaluation_target": target,
        "diagnostics": _sort_diagnostics(diagnostics),
    }))


def evaluate_generated_reasoning_model(model: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_reasoning_model(model)


def validate_reasoning_runtime_result(result: dict[str, Any] | str | Path) -> dict[str, Any]:
    value = _load_json(result)
    diagnostics: list[dict[str, Any]] = []
    if not isinstance(value, dict):
        diagnostics.append(_diag("RRP-001", "missing schema_version", location="schema_version"))
        return _validation_result(diagnostics)

    _check_top_level(value, diagnostics)
    _check_source_ref(value.get("source_ref"), diagnostics)
    _check_pipeline_status(value.get("pipeline_status"), diagnostics)
    _check_nested_model(value.get("reasoning_model"), diagnostics)
    _check_nested_report(value.get("evaluation_report"), diagnostics)
    _check_diagnostics(value.get("diagnostics"), diagnostics)
    return _validation_result(_sort_diagnostics(diagnostics))


def serialize_reasoning_runtime_result(result: dict[str, Any]) -> str:
    return json.dumps(_canonicalize(result), ensure_ascii=False, indent=2) + "\n"


def render_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def _artifact_bundle(source_or_artifacts: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source_or_artifacts, dict):
        return source_or_artifacts
    path = Path(source_or_artifacts)
    return _analyze_result(path, "normal")


def _source_ref(bundle: dict[str, Any]) -> dict[str, Any]:
    explicit = bundle.get("source_ref")
    if isinstance(explicit, dict):
        source_id = str(explicit.get("source_id") or "runtime_source")
        source_kind = str(explicit.get("source_kind") or "pipeline_artifact_bundle")
        ref = {"source_id": source_id, "source_kind": source_kind}
        if explicit.get("source_path"):
            ref["source_path"] = explicit["source_path"]
        return ref
    source_file = str(bundle.get("source_file") or "pipeline_artifact_bundle")
    return {
        "source_id": _slug(Path(source_file).stem or "runtime_source"),
        "source_kind": "reason_script_source" if source_file.endswith(".rsn") else "pipeline_artifact_bundle",
        "source_path": source_file,
    }


def _pipeline_status(bundle: dict[str, Any], diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    payload = bundle.get("artifacts") if isinstance(bundle.get("artifacts"), dict) else bundle
    parser_passed = bool(bundle.get("ok", True)) and not any(item["code"] == "RRP-PIPE-001" for item in diagnostics)
    status = "passed"
    if any(item["severity"] == "fatal" for item in diagnostics) or not parser_passed:
        status = "fatal"
    elif any(item["severity"] == "error" for item in diagnostics):
        status = "failed"
    elif any(item["severity"] == "warning" for item in diagnostics):
        status = "partial"
    return {
        "status": status,
        "parser_passed": parser_passed,
        "reason_ir_available": isinstance(payload.get("reason_ir"), dict),
        "execution_plan_available": isinstance(payload.get("execution_plan"), dict),
        "simulation_available": isinstance(payload.get("simulation"), dict),
        "knowledge_available": isinstance(payload.get("knowledge"), dict),
        "diagnostics_count": len(bundle.get("diagnostics", [])) if isinstance(bundle.get("diagnostics"), list) else 0,
    }


def _pipeline_diagnostics(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    payload = bundle.get("artifacts") if isinstance(bundle.get("artifacts"), dict) else bundle
    diagnostics: list[dict[str, Any]] = []
    if bundle.get("ok") is False:
        diagnostics.append(_diag("RRP-PIPE-001", "Parser or pipeline execution failed", severity="fatal", location="source"))
    for key, code, message, severity in (
        ("reason_ir", "RRP-PIPE-002", "Reason IR unavailable", "error"),
        ("execution_plan", "RRP-PIPE-003", "ExecutionPlan unavailable", "error"),
        ("simulation", "RRP-PIPE-004", "Simulation unavailable", "error"),
        ("knowledge", "RRP-PIPE-005", "Knowledge unavailable", "warning"),
    ):
        if not isinstance(payload.get(key), dict):
            diagnostics.append(_diag(code, message, severity=severity, location=key))
    upstream = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), list) else []
    if any(str(item.get("severity", "")).lower() == "fatal" for item in upstream if isinstance(item, dict)):
        diagnostics.append(_diag("RRP-PIPE-006", "Upstream diagnostics contain fatal error", severity="fatal", location="diagnostics"))
    return diagnostics


def _input_units_and_relations(
    reason_ir: dict[str, Any],
    execution_plan: dict[str, Any],
    knowledge: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unit_types: dict[str, str] = {}
    for state in (reason_ir.get("initial_state", {}).get("state_id"), execution_plan.get("goal")):
        if state:
            unit_types[str(state)] = "state"
    for transition in _as_list(reason_ir.get("transitions")):
        if not isinstance(transition, dict):
            continue
        for key in ("source", "target"):
            if transition.get(key):
                unit_types[str(transition[key])] = "state"
        effect = transition.get("effect") if isinstance(transition.get("effect"), dict) else {}
        if effect.get("calculation"):
            unit_types[str(transition.get("target"))] = "calculation_result"
        if transition.get("relation") == "FunctionReturnTransition":
            unit_types[str(transition.get("target"))] = "function_return"
    for item in _knowledge_items(knowledge):
        for key in ("source", "target"):
            if item.get(key):
                unit_types.setdefault(str(item[key]), "knowledge_entity")

    units = [
        {"unit_id": unit_id, "unit_type": unit_types[unit_id], "value": unit_id}
        for unit_id in sorted(unit_types)
        if unit_id and unit_id != "None"
    ]
    unit_ids = {item["unit_id"] for item in units}
    relations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, transition in enumerate(_as_list(reason_ir.get("transitions")), start=1):
        if not isinstance(transition, dict):
            continue
        source = str(transition.get("source") or "")
        target = str(transition.get("target") or "")
        relation = str(transition.get("relation") or "transition")
        key = (source, target, relation)
        if source in unit_ids and target in unit_ids and key not in seen:
            relations.append({"relation_id": f"rel_{index:03d}", "relation_type": relation, "source": source, "target": target})
            seen.add(key)
    return units, relations


def _reasoning_steps(execution_plan: dict[str, Any], reason_ir: dict[str, Any], simulation: dict[str, Any]) -> list[dict[str, Any]]:
    transition_by_id = {
        item.get("transition_id"): item
        for item in _as_list(reason_ir.get("transitions"))
        if isinstance(item, dict) and item.get("transition_id")
    }
    selected_steps = [item for item in _as_list(execution_plan.get("selected_steps")) if isinstance(item, dict)]
    steps: list[dict[str, Any]] = []
    for index, selected in enumerate(selected_steps, start=1):
        transition = transition_by_id.get(selected.get("transition_id"), {})
        step_type = _step_type(selected, transition, simulation)
        step_id = str(selected.get("step_id") or f"step-{index}")
        steps.append({
            "step_id": step_id,
            "step_type": step_type,
            "source": selected.get("source"),
            "target": selected.get("target"),
            "operation": transition.get("relation") or selected.get("transition_id") or "transition",
            "evidence_refs": [ref for ref in (selected.get("transition_id"),) if ref],
        })
    return steps


def _step_type(selected: dict[str, Any], transition: dict[str, Any], simulation: dict[str, Any]) -> str:
    transition_id = selected.get("transition_id")
    relation = transition.get("relation")
    if relation == "FunctionReturnTransition":
        effect = transition.get("effect") if isinstance(transition.get("effect"), dict) else {}
        return "branch_selection" if effect.get("branch_conditions") else "function_return"
    if transition_id in set(_as_list(simulation.get("selected_branches"))):
        return "branch_selection"
    if relation == "ResultTransition":
        return "calculation"
    if relation:
        return "relation_check"
    return "state_transition"


def _knowledge_emissions(knowledge: dict[str, Any], steps: list[dict[str, Any]], path_signature: str) -> list[dict[str, Any]]:
    if not steps:
        return []
    step_by_target = {step.get("target"): step.get("step_id") for step in steps}
    final_step = steps[-1]["step_id"]
    emissions = []
    for index, item in enumerate(_knowledge_items(knowledge), start=1):
        knowledge_id = str(item.get("id") or f"knowledge_{index:03d}")
        source_step_id = step_by_target.get(item.get("target")) or final_step
        evidence_path = [source_step_id]
        for ref in _as_list(item.get("evidence_path")):
            matched = step_by_target.get(ref)
            if matched and matched not in evidence_path:
                evidence_path.insert(0, matched)
        emissions.append({
            "knowledge_id": knowledge_id,
            "source_step_id": source_step_id,
            "relation": str(item.get("relation") or "emits"),
            "source": str(item.get("source") or ""),
            "target": str(item.get("target") or ""),
            "evidence_path": evidence_path,
            "path_signature": path_signature,
        })
    return emissions


def _evaluation_target(
    execution_plan: dict[str, Any],
    simulation: dict[str, Any],
    emissions: list[dict[str, Any]],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    goal = execution_plan.get("goal") or simulation.get("final_state")
    if not goal and emissions:
        goal = emissions[-1].get("target")
    if not goal and steps:
        goal = steps[-1].get("target")
    target: dict[str, Any] = {
        "target_id": "eval_001",
        "goal": str(goal or "unknown"),
        "required_checks": REQUIRED_CHECKS,
    }
    if emissions:
        last = emissions[-1]
        target["expected_relation"] = {
            "relation": last.get("relation"),
            "source": last.get("source"),
            "target": last.get("target"),
        }
    return target


def _path_signature(execution_plan: dict[str, Any], simulation: dict[str, Any], steps: list[dict[str, Any]]) -> str:
    signature = execution_plan.get("path_signature") or simulation.get("path_signature")
    if signature:
        return str(signature)
    return ".".join(str(step.get("target")) for step in steps if step.get("target")) or "path_main"


def _module_name(reason_ir: dict[str, Any], bundle: dict[str, Any]) -> str | None:
    metadata = reason_ir.get("metadata") if isinstance(reason_ir.get("metadata"), dict) else {}
    initial = reason_ir.get("initial_state") if isinstance(reason_ir.get("initial_state"), dict) else {}
    data = initial.get("data") if isinstance(initial.get("data"), dict) else {}
    return metadata.get("module") or data.get("module") or Path(str(bundle.get("source_file") or "")).stem


def _knowledge_items(knowledge: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(knowledge.get("knowledge")) if isinstance(item, dict)]


def _check_top_level(value: dict[str, Any], diagnostics: list[dict[str, Any]]) -> None:
    if "schema_version" not in value:
        diagnostics.append(_diag("RRP-001", "missing schema_version", location="schema_version"))
    elif value.get("schema_version") != CONTRACT_SCHEMA:
        diagnostics.append(_diag("RRP-002", "unsupported schema_version", location="schema_version"))
    for field, code in (
        ("run_id", "RRP-003"),
        ("source_ref", "RRP-004"),
        ("pipeline_status", "RRP-005"),
        ("reasoning_model", "RRP-006"),
        ("evaluation_report", "RRP-007"),
        ("diagnostics", "RRP-008"),
    ):
        if field not in value:
            diagnostics.append(_diag(code, f"missing {field}", location=field))
    if not isinstance(value.get("run_id"), str) or not value.get("run_id", "").strip():
        diagnostics.append(_diag("RRP-003", "missing run_id", location="run_id"))


def _check_source_ref(source_ref: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(source_ref, dict):
        return
    if not isinstance(source_ref.get("source_id"), str) or not source_ref.get("source_id"):
        diagnostics.append(_diag("RRP-004", "missing source_ref.source_id", location="source_ref.source_id"))
    if source_ref.get("source_kind") not in SOURCE_KINDS:
        diagnostics.append(_diag("RRP-004", "invalid source_ref.source_kind", location="source_ref.source_kind"))


def _check_pipeline_status(status: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(status, dict):
        return
    if status.get("status") not in PIPELINE_STATUSES:
        diagnostics.append(_diag("RRP-PIPE-STATUS", "invalid pipeline status", location="pipeline_status.status"))
    required = (
        "parser_passed",
        "reason_ir_available",
        "execution_plan_available",
        "simulation_available",
        "knowledge_available",
    )
    missing_required = any(status.get(field) is not True for field in required[:4])
    if status.get("status") == "passed" and missing_required:
        diagnostics.append(_diag("RRP-PIPE-INCONSISTENT", "pipeline_status is inconsistent with required artifact availability", location="pipeline_status"))
    if not isinstance(status.get("diagnostics_count"), int):
        diagnostics.append(_diag("RRP-PIPE-INCONSISTENT", "pipeline_status.diagnostics_count must be an integer", location="pipeline_status.diagnostics_count"))


def _check_nested_model(model: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(model, dict) or not model:
        return
    result = validate_reasoning_model(model)
    if not result["valid"]:
        diagnostics.append(_diag("RRP-PROJ-007", "Generated ReasoningModel failed validation", location="reasoning_model"))


def _check_nested_report(report: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(report, dict) or not report:
        return
    result = validate_evaluation_report(report)
    if not result["valid"]:
        diagnostics.append(_diag("RRP-EVAL-002", "Generated ReasoningEvaluationReport failed validation", location="evaluation_report"))


def _check_diagnostics(items: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(items, list):
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            diagnostics.append(_diag("RRP-008", "diagnostic must be an object", location=f"diagnostics[{index}]"))
            continue
        for field in ("code", "severity", "message"):
            if not item.get(field):
                diagnostics.append(_diag("RRP-008", f"diagnostic missing {field}", location=f"diagnostics[{index}].{field}"))
        if item.get("severity") and item.get("severity") not in SEVERITIES:
            diagnostics.append(_diag("RRP-008", "diagnostic severity is invalid", location=f"diagnostics[{index}].severity"))


def _canonicalize(value: Any) -> Any:
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _canonicalize(item) for key, item in value.items()}
    if "schema_version" in result and "run_id" in result and "pipeline_status" in result:
        result["diagnostics"] = _sort_diagnostics(_as_list(result.get("diagnostics")))
        return _reorder(result, TOP_LEVEL_ORDER)
    if {"source_id", "source_kind"}.issubset(result):
        return _reorder(result, SOURCE_REF_ORDER)
    if "parser_passed" in result and "reason_ir_available" in result:
        return _reorder(result, PIPELINE_STATUS_ORDER)
    if {"code", "severity", "message"}.issubset(result):
        return _reorder(result, DIAGNOSTIC_ORDER)
    return {key: result[key] for key in sorted(result)}


def _reorder(value: dict[str, Any], order: tuple[str, ...]) -> dict[str, Any]:
    ordered = {key: value[key] for key in order if key in value}
    for key in sorted(value):
        if key not in ordered:
            ordered[key] = value[key]
    return ordered


def _validation_result(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": VALIDATOR_SCHEMA,
        "valid": not any(item["severity"] in FAILING_SEVERITIES for item in diagnostics),
        "diagnostics": diagnostics,
    }


def _diag(code: str, message: str, *, severity: str = "error", location: str | None = None) -> dict[str, Any]:
    diagnostic = {"code": code, "severity": severity, "message": message}
    if location is not None:
        diagnostic["location"] = location
    return diagnostic


def _sort_diagnostics(diagnostics: list[Any]) -> list[dict[str, Any]]:
    return sorted(
        [item for item in diagnostics if isinstance(item, dict)],
        key=lambda item: (str(item.get("code", "")), str(item.get("location", "")), str(item.get("message", ""))),
    )


def _load_json(source: dict[str, Any] | str | Path) -> Any:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_")
    return slug or "runtime_source"
