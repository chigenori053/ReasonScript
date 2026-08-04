"""Reasoning Evaluation Report contract and evaluator for Phase 8B.

This module evaluates existing ReasoningModel artifacts. It intentionally does
not parse or execute ReasonScript source and does not alter runtime semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toolchain.reasoning_model_contract import (
    CONTRACT_SCHEMA as MODEL_SCHEMA,
)
from toolchain.reasoning_model_contract import (
    REQUIRED_CHECKS as MODEL_REQUIRED_CHECKS,
)
from toolchain.reasoning_model_contract import (
    serialize_reasoning_model,
)
from toolchain.reasoning_model_contract import (
    validate as validate_reasoning_model,
)

CONTRACT_SCHEMA = "reasonscript-reasoning-evaluation-report/1.0"
VALIDATOR_SCHEMA = "reasonscript-reasoning-evaluation-report-validator/1.0"

CHECK_TYPES = (
    "reachability",
    "determinism",
    "evidence_completeness",
    "consistency",
    "minimality",
    "branch_traceability",
)
CHECK_STATUSES = ("passed", "failed", "warning", "skipped", "fatal")
SUMMARY_STATUSES = ("passed", "failed", "warning", "fatal")
SEVERITIES = ("info", "warning", "error", "fatal")
FAILING_SEVERITIES = ("error", "fatal")

TOP_LEVEL_ORDER = (
    "schema_version",
    "report_id",
    "model_ref",
    "evaluation_target_ref",
    "summary",
    "checks",
    "diagnostics",
    "metadata",
)
MODEL_REF_ORDER = ("model_id", "model_schema_version", "source_id")
TARGET_REF_ORDER = ("target_id", "goal", "required_checks")
SUMMARY_ORDER = (
    "status",
    "passed",
    "required_checks_passed",
    "total_checks",
    "passed_checks",
    "failed_checks",
    "warning_checks",
    "fatal_diagnostics",
)
CHECK_ORDER = (
    "check_id",
    "check_type",
    "required",
    "status",
    "passed",
    "message",
    "evidence_refs",
    "details",
)
DIAGNOSTIC_ORDER = ("code", "severity", "message", "location")


def load_json(source: dict[str, Any] | str | Path) -> Any:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def evaluate_reasoning_model(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    model = load_json(source)
    if not isinstance(model, dict):
        return _fatal_report(
            model_id="unknown",
            target={},
            diagnostics=[_diag("ER-EVAL-001", "invalid ReasoningModel artifact", severity="fatal", location="$")],
        )

    model_result = validate_reasoning_model(model)
    target = model.get("evaluation_target") if isinstance(model.get("evaluation_target"), dict) else {}
    required_checks = [check for check in _as_list(target.get("required_checks")) if isinstance(check, str)]
    if not required_checks:
        required_checks = ["reachability", "determinism", "evidence_completeness", "consistency"]

    diagnostics: list[dict[str, Any]] = []
    if model.get("schema_version") != MODEL_SCHEMA:
        diagnostics.append(_diag("ER-EVAL-002", "unsupported ReasoningModel version", severity="fatal", location="schema_version"))
    elif not model_result.get("valid", False):
        diagnostics.append(_diag("ER-EVAL-001", "invalid ReasoningModel artifact", severity="fatal", location="$"))

    checks = [_run_check(check_type, model, target) for check_type in required_checks]
    checks = _sort_checks(checks)
    return _report(model, target, checks, diagnostics)


def validate_evaluation_report(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    report = load_json(source)
    diagnostics: list[dict[str, Any]] = []
    if not isinstance(report, dict):
        diagnostics.append(_diag("ER-001", "missing schema_version", location="schema_version"))
        return _validation_result(diagnostics)

    _check_report_top_level(report, diagnostics)
    _check_model_ref(report.get("model_ref"), diagnostics)
    _check_target_ref(report.get("evaluation_target_ref"), diagnostics)
    _check_checks(report.get("checks"), report.get("evaluation_target_ref"), report.get("diagnostics"), diagnostics)
    _check_summary(report.get("summary"), report.get("checks"), report.get("diagnostics"), diagnostics)
    _check_report_diagnostics(report.get("diagnostics"), diagnostics)
    return _validation_result(_sort_diagnostics(diagnostics))


def serialize_evaluation_report(report: dict[str, Any]) -> str:
    return json.dumps(_canonicalize(report), ensure_ascii=False, indent=2) + "\n"


def render_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def _run_check(check_type: str, model: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    if check_type == "reachability":
        return _reachability(model, target)
    if check_type == "determinism":
        return _determinism(model)
    if check_type == "evidence_completeness":
        return _evidence_completeness(model)
    if check_type == "consistency":
        return _consistency(model, target)
    if check_type == "minimality":
        return _minimality(model)
    if check_type == "branch_traceability":
        return _branch_traceability(model)
    return _check(
        check_type=check_type,
        status="failed",
        message=f"Unsupported required check: {check_type}.",
        evidence_refs=[],
        details={"supported": False},
    )


def _reachability(model: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    goal = target.get("goal")
    selected_path_id = model.get("selected_path_id")
    selected_path = _selected_path(model)
    if not selected_path:
        return _check(
            check_type="reachability",
            status="failed",
            message="Selected reasoning path was not found.",
            evidence_refs=[],
            details={"goal": goal, "selected_path_id": selected_path_id, "reachable": False},
        )
    steps = _as_list(selected_path.get("steps"))
    if not steps:
        return _check(
            check_type="reachability",
            status="failed",
            message="Selected reasoning path has no steps.",
            evidence_refs=[selected_path_id] if selected_path_id else [],
            details={"goal": goal, "selected_path_id": selected_path_id, "reachable": False},
        )

    for step in steps:
        if isinstance(step, dict) and step.get("target") == goal:
            return _check(
                check_type="reachability",
                status="passed",
                message="Selected reasoning path reaches the evaluation goal.",
                evidence_refs=[selected_path_id, step.get("step_id")],
                details={
                    "goal": goal,
                    "selected_path_id": selected_path_id,
                    "reachable": True,
                    "matched_by": "reasoning_step",
                    "matched_ref": step.get("step_id"),
                },
            )

    for emission in _as_list(model.get("knowledge_emissions")):
        if isinstance(emission, dict) and emission.get("target") == goal:
            return _check(
                check_type="reachability",
                status="passed",
                message="Selected reasoning path reaches the evaluation goal.",
                evidence_refs=[selected_path_id, emission.get("knowledge_id")],
                details={
                    "goal": goal,
                    "selected_path_id": selected_path_id,
                    "reachable": True,
                    "matched_by": "knowledge_emission",
                    "matched_ref": emission.get("knowledge_id"),
                },
            )

    expected_relation = target.get("expected_relation")
    if isinstance(expected_relation, dict):
        for emission in _as_list(model.get("knowledge_emissions")):
            if _relation_matches(emission, expected_relation):
                return _check(
                    check_type="reachability",
                    status="passed",
                    message="Selected reasoning path produces the expected relation.",
                    evidence_refs=[selected_path_id, emission.get("knowledge_id")],
                    details={
                        "goal": goal,
                        "selected_path_id": selected_path_id,
                        "reachable": True,
                        "matched_by": "expected_relation",
                        "matched_ref": emission.get("knowledge_id"),
                    },
                )

    return _check(
        check_type="reachability",
        status="failed",
        message="Evaluation goal is unreachable from the selected reasoning path.",
        evidence_refs=[selected_path_id] if selected_path_id else [],
        details={"goal": goal, "selected_path_id": selected_path_id, "reachable": False},
    )


def _determinism(model: dict[str, Any]) -> dict[str, Any]:
    duplicates = _duplicate_ids(model)
    stable_ids = bool(model.get("model_id")) and bool(model.get("selected_path_id"))
    selected_matches = [path for path in _as_list(model.get("reasoning_paths")) if isinstance(path, dict) and path.get("path_id") == model.get("selected_path_id")]
    stable_serialization = serialize_reasoning_model(model) == serialize_reasoning_model(json.loads(serialize_reasoning_model(model)))
    passed = stable_ids and not duplicates and len(selected_matches) == 1 and stable_serialization
    return _check(
        check_type="determinism",
        status="passed" if passed else "failed",
        message="ReasoningModel artifact is deterministically representable." if passed else "ReasoningModel artifact is not deterministically representable.",
        evidence_refs=[model.get("model_id")] if model.get("model_id") else [],
        details={
            "stable_ids": stable_ids,
            "duplicate_ids": duplicates,
            "canonical_serialization_stable": stable_serialization,
        },
    )


def _evidence_completeness(model: dict[str, Any]) -> dict[str, Any]:
    paths = _as_list(model.get("reasoning_paths"))
    path_signatures = {path.get("path_signature") for path in paths if isinstance(path, dict)}
    steps = [step for path in paths if isinstance(path, dict) for step in _as_list(path.get("steps")) if isinstance(step, dict)]
    step_ids = {step.get("step_id") for step in steps}
    emissions = [item for item in _as_list(model.get("knowledge_emissions")) if isinstance(item, dict)]

    missing_evidence_refs = [step.get("step_id") for step in steps if "evidence_refs" not in step]
    missing_evidence_paths = [item.get("knowledge_id") for item in emissions if not item.get("evidence_path")]
    invalid_source_step_refs = [item.get("knowledge_id") for item in emissions if item.get("source_step_id") not in step_ids]
    invalid_path_signatures = [item.get("knowledge_id") for item in emissions if item.get("path_signature") not in path_signatures]
    failures = missing_evidence_refs + missing_evidence_paths + invalid_source_step_refs + invalid_path_signatures
    return _check(
        check_type="evidence_completeness",
        status="passed" if not failures else "failed",
        message="Knowledge emissions include complete evidence paths." if not failures else "ReasoningModel evidence is incomplete.",
        evidence_refs=sorted([ref for ref in list(step_ids) + [item.get("knowledge_id") for item in emissions] if ref]),
        details={
            "steps_checked": len(steps),
            "knowledge_emissions_checked": len(emissions),
            "missing_evidence_refs": sorted(missing_evidence_refs),
            "missing_evidence_paths": sorted(missing_evidence_paths),
            "invalid_source_step_refs": sorted(invalid_source_step_refs),
            "invalid_path_signatures": sorted(invalid_path_signatures),
        },
    )


def _consistency(model: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    paths = [path for path in _as_list(model.get("reasoning_paths")) if isinstance(path, dict)]
    path_ids = {path.get("path_id") for path in paths}
    signatures = {path.get("path_signature") for path in paths}
    selected_path_valid = model.get("selected_path_id") in path_ids
    selected_path_count = len([path for path in paths if path.get("status") == "selected"])
    input_relations_valid = _input_relations_valid(model)
    unknown_checks = [check for check in _as_list(target.get("required_checks")) if check not in CHECK_TYPES]
    unknown_signatures = [
        item.get("knowledge_id")
        for item in _as_list(model.get("knowledge_emissions"))
        if isinstance(item, dict) and item.get("path_signature") not in signatures
    ]
    fatal_model_diagnostics = len([
        item for item in _as_list(model.get("diagnostics"))
        if isinstance(item, dict) and item.get("severity") == "fatal"
    ])
    passed = (
        selected_path_valid
        and selected_path_count == 1
        and input_relations_valid
        and not unknown_checks
        and not unknown_signatures
        and fatal_model_diagnostics == 0
    )
    return _check(
        check_type="consistency",
        status="passed" if passed else "failed",
        message="ReasoningModel artifact is structurally consistent." if passed else "ReasoningModel artifact has structural consistency failures.",
        evidence_refs=sorted([path_id for path_id in path_ids if path_id]),
        details={
            "selected_path_valid": selected_path_valid,
            "selected_path_count": selected_path_count,
            "input_relations_valid": input_relations_valid,
            "unknown_required_checks": sorted(unknown_checks),
            "unknown_path_signatures": sorted(unknown_signatures),
            "fatal_model_diagnostics": fatal_model_diagnostics,
        },
    )


def _minimality(model: dict[str, Any]) -> dict[str, Any]:
    selected_path = _selected_path(model)
    steps = _as_list(selected_path.get("steps")) if selected_path else []
    signatures = [_step_signature(step) for step in steps if isinstance(step, dict)]
    duplicate_signatures = sorted({signature for signature in signatures if signatures.count(signature) > 1})
    evidence_step_ids = {
        ref
        for emission in _as_list(model.get("knowledge_emissions"))
        if isinstance(emission, dict)
        for ref in _as_list(emission.get("evidence_path"))
    }
    unreferenced = sorted([
        step.get("step_id")
        for step in steps
        if isinstance(step, dict) and step.get("step_id") not in evidence_step_ids and step.get("target") != model.get("evaluation_target", {}).get("goal")
    ])
    status = "passed" if steps and not duplicate_signatures else "failed"
    return _check(
        check_type="minimality",
        status=status,
        message="Selected reasoning path is artifact-minimal." if status == "passed" else "Selected reasoning path contains duplicate step signatures.",
        evidence_refs=[selected_path.get("path_id")] if selected_path else [],
        details={
            "selected_path_id": selected_path.get("path_id") if selected_path else model.get("selected_path_id"),
            "step_count": len(steps),
            "duplicate_step_signatures": duplicate_signatures,
            "unreferenced_steps": unreferenced,
        },
    )


def _branch_traceability(model: dict[str, Any]) -> dict[str, Any]:
    decisions = _branch_decisions(model)
    if not decisions:
        return _check(
            check_type="branch_traceability",
            status="passed",
            message="No branch decisions are present.",
            evidence_refs=[],
            details={"branch_decisions_checked": 0, "branches_traceable": True, "missing_branch_evidence": []},
        )
    paths = [path for path in _as_list(model.get("reasoning_paths")) if isinstance(path, dict)]
    known = {path.get("path_id") for path in paths} | {path.get("path_signature") for path in paths}
    missing_evidence = []
    invalid_selected = []
    for decision in decisions:
        branch_id = decision.get("branch_id") or decision.get("decision_point")
        if not decision.get("selected") or "rejected" not in decision or "evidence_refs" not in decision:
            missing_evidence.append(branch_id)
        if decision.get("selected") not in known:
            invalid_selected.append(branch_id)
    failures = missing_evidence + invalid_selected
    return _check(
        check_type="branch_traceability",
        status="passed" if not failures else "failed",
        message="Branch decisions are traceable." if not failures else "Branch decisions are not traceable.",
        evidence_refs=sorted([ref for decision in decisions for ref in _as_list(decision.get("evidence_refs"))]),
        details={
            "branch_decisions_checked": len(decisions),
            "branches_traceable": not failures,
            "missing_branch_evidence": sorted(missing_evidence),
            "invalid_selected_branches": sorted(invalid_selected),
        },
    )


def _report(
    model: dict[str, Any],
    target: dict[str, Any],
    checks: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "report_id": f"report_{model.get('model_id', 'unknown')}_{target.get('target_id', 'unknown')}",
        "model_ref": {
            "model_id": model.get("model_id", "unknown"),
            "model_schema_version": model.get("schema_version", ""),
            **({"source_id": model.get("source_ref", {}).get("source_id")} if isinstance(model.get("source_ref"), dict) and model.get("source_ref", {}).get("source_id") else {}),
        },
        "evaluation_target_ref": {
            "target_id": target.get("target_id", "unknown"),
            "goal": target.get("goal", ""),
            "required_checks": [check.get("check_type") for check in checks],
        },
        "summary": _summary(checks, diagnostics),
        "checks": checks,
        "diagnostics": _sort_diagnostics(diagnostics),
    }


def _fatal_report(model_id: str, target: dict[str, Any], diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "report_id": f"report_{model_id}_{target.get('target_id', 'unknown')}",
        "model_ref": {"model_id": model_id, "model_schema_version": ""},
        "evaluation_target_ref": {"target_id": target.get("target_id", "unknown"), "goal": target.get("goal", ""), "required_checks": []},
        "summary": _summary([], diagnostics),
        "checks": [],
        "diagnostics": diagnostics,
    }


def _summary(checks: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    passed_checks = len([check for check in checks if check.get("status") == "passed"])
    failed_checks = len([check for check in checks if check.get("status") in {"failed", "fatal"}])
    warning_checks = len([check for check in checks if check.get("status") == "warning"])
    fatal_diagnostics = len([item for item in diagnostics if item.get("severity") == "fatal"])
    required_checks_passed = all(
        check.get("status") == "passed" for check in checks if check.get("required") is True
    )
    if fatal_diagnostics:
        status = "fatal"
    elif not required_checks_passed:
        status = "failed"
    elif warning_checks:
        status = "warning"
    else:
        status = "passed"
    return {
        "status": status,
        "passed": status == "passed",
        "required_checks_passed": required_checks_passed,
        "total_checks": len(checks),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "warning_checks": warning_checks,
        "fatal_diagnostics": fatal_diagnostics,
    }


def _check(*, check_type: str, status: str, message: str, evidence_refs: list[Any], details: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": f"check_{check_type}",
        "check_type": check_type,
        "required": True,
        "status": status,
        "passed": status == "passed",
        "message": message,
        "evidence_refs": [str(ref) for ref in evidence_refs if ref],
        "details": details,
    }


def _validation_result(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": VALIDATOR_SCHEMA,
        "valid": not any(item["severity"] in FAILING_SEVERITIES for item in diagnostics),
        "diagnostics": diagnostics,
    }


def _check_report_top_level(report: dict[str, Any], diagnostics: list[dict[str, Any]]) -> None:
    required = (
        ("schema_version", "ER-001", "missing schema_version"),
        ("report_id", "ER-003", "missing report_id"),
        ("model_ref", "ER-004", "missing model_ref"),
        ("evaluation_target_ref", "ER-005", "missing evaluation_target_ref"),
        ("summary", "ER-006", "missing summary"),
        ("checks", "ER-007", "missing checks"),
        ("diagnostics", "ER-008", "missing diagnostics"),
    )
    for field, code, message in required:
        if field not in report:
            diagnostics.append(_diag(code, message, location=field))
    if "schema_version" in report and report.get("schema_version") != CONTRACT_SCHEMA:
        diagnostics.append(_diag("ER-002", "unsupported schema_version", location="schema_version"))


def _check_model_ref(model_ref: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(model_ref, dict):
        return
    if not model_ref.get("model_id"):
        diagnostics.append(_diag("ER-MODEL-001", "missing model_id", location="model_ref.model_id"))
    if not model_ref.get("model_schema_version"):
        diagnostics.append(_diag("ER-MODEL-002", "missing model_schema_version", location="model_ref.model_schema_version"))
    elif model_ref.get("model_schema_version") != MODEL_SCHEMA:
        diagnostics.append(_diag("ER-MODEL-003", "unsupported model_schema_version", location="model_ref.model_schema_version"))


def _check_target_ref(target_ref: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(target_ref, dict):
        return
    if not target_ref.get("target_id"):
        diagnostics.append(_diag("ER-TARGET-001", "missing target_id", location="evaluation_target_ref.target_id"))
    if not target_ref.get("goal"):
        diagnostics.append(_diag("ER-TARGET-002", "missing goal", location="evaluation_target_ref.goal"))
    required_checks = target_ref.get("required_checks")
    if not isinstance(required_checks, list):
        diagnostics.append(_diag("ER-TARGET-003", "missing required_checks", location="evaluation_target_ref.required_checks"))
        return
    for check in required_checks:
        if check not in CHECK_TYPES:
            diagnostics.append(_diag("ER-TARGET-004", f"invalid required_check: {check}", location="evaluation_target_ref.required_checks"))


def _check_checks(checks: Any, target_ref: Any, report_diagnostics: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(checks, list):
        return
    seen: set[str] = set()
    by_type: dict[str, dict[str, Any]] = {}
    has_fatal = any(isinstance(item, dict) and item.get("severity") == "fatal" for item in _as_list(report_diagnostics))
    for check in checks:
        if not isinstance(check, dict):
            continue
        check_id = check.get("check_id")
        if check_id in seen:
            diagnostics.append(_diag("ER-CHECK-001", f"duplicate check_id: {check_id}", location="checks"))
        seen.add(check_id)
        check_type = check.get("check_type")
        if not check_type:
            diagnostics.append(_diag("ER-CHECK-002", "missing check_type", location="checks.check_type"))
        elif check_type not in CHECK_TYPES:
            diagnostics.append(_diag("ER-CHECK-003", f"invalid check_type: {check_type}", location="checks.check_type"))
        else:
            by_type[check_type] = check
        status = check.get("status")
        if not status:
            diagnostics.append(_diag("ER-CHECK-004", "missing check status", location="checks.status"))
        elif status not in CHECK_STATUSES:
            diagnostics.append(_diag("ER-CHECK-005", f"invalid check status: {status}", location="checks.status"))
        if "passed" not in check:
            diagnostics.append(_diag("ER-CHECK-006", "missing passed flag", location="checks.passed"))
        elif check.get("passed") is not (status == "passed"):
            diagnostics.append(_diag("ER-CHECK-007", "passed flag inconsistent with check status", location="checks.passed"))
        if check.get("required") is True and status == "skipped" and not has_fatal:
            diagnostics.append(_diag("ER-CHECK-009", "required check skipped without fatal diagnostic", location="checks.status"))

    if isinstance(target_ref, dict):
        for required in _as_list(target_ref.get("required_checks")):
            if required in CHECK_TYPES and required not in by_type:
                diagnostics.append(_diag("ER-CHECK-008", f"missing required check result: {required}", location="checks"))


def _check_summary(summary: Any, checks: Any, report_diagnostics: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(summary, dict):
        return
    if "status" not in summary:
        diagnostics.append(_diag("ER-SUM-001", "missing status", location="summary.status"))
    elif summary.get("status") not in SUMMARY_STATUSES:
        diagnostics.append(_diag("ER-SUM-002", f"invalid status: {summary.get('status')}", location="summary.status"))
    if "passed" not in summary:
        diagnostics.append(_diag("ER-SUM-003", "missing passed", location="summary.passed"))
    if "required_checks_passed" not in summary:
        diagnostics.append(_diag("ER-SUM-004", "missing required_checks_passed", location="summary.required_checks_passed"))

    actual_checks = _as_list(checks)
    passed_checks = len([check for check in actual_checks if isinstance(check, dict) and check.get("status") == "passed"])
    failed_checks = len([check for check in actual_checks if isinstance(check, dict) and check.get("status") in {"failed", "fatal"}])
    warning_checks = len([check for check in actual_checks if isinstance(check, dict) and check.get("status") == "warning"])
    fatal_diagnostics = len([item for item in _as_list(report_diagnostics) if isinstance(item, dict) and item.get("severity") == "fatal"])
    expected_counts = {
        "total_checks": len(actual_checks),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "warning_checks": warning_checks,
        "fatal_diagnostics": fatal_diagnostics,
    }
    for field, expected in expected_counts.items():
        if summary.get(field) != expected:
            diagnostics.append(_diag("ER-SUM-005", f"invalid check count: {field}", location=f"summary.{field}"))
            break

    required_checks_passed = all(
        isinstance(check, dict) and check.get("status") == "passed"
        for check in actual_checks
        if isinstance(check, dict) and check.get("required") is True
    )
    if fatal_diagnostics:
        expected_status = "fatal"
    elif not required_checks_passed:
        expected_status = "failed"
    elif warning_checks:
        expected_status = "warning"
    else:
        expected_status = "passed"
    if summary.get("status") in SUMMARY_STATUSES and summary.get("status") != expected_status:
        diagnostics.append(_diag("ER-SUM-006", "summary status inconsistent with check results", location="summary.status"))
    if "passed" in summary and summary.get("passed") is not (summary.get("status") == "passed"):
        diagnostics.append(_diag("ER-SUM-007", "passed flag inconsistent with status", location="summary.passed"))


def _check_report_diagnostics(report_diagnostics: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(report_diagnostics, list):
        return
    for item in report_diagnostics:
        if not isinstance(item, dict):
            continue
        if item.get("severity") not in SEVERITIES:
            diagnostics.append(_diag("ER-SUM-006", f"invalid diagnostic severity: {item.get('severity')}", location="diagnostics.severity"))


def _selected_path(model: dict[str, Any]) -> dict[str, Any] | None:
    selected_path_id = model.get("selected_path_id")
    for path in _as_list(model.get("reasoning_paths")):
        if isinstance(path, dict) and path.get("path_id") == selected_path_id:
            return path
    return None


def _relation_matches(emission: Any, relation: dict[str, Any]) -> bool:
    return isinstance(emission, dict) and all(emission.get(key) == value for key, value in relation.items())


def _duplicate_ids(model: dict[str, Any]) -> list[str]:
    duplicates: list[str] = []
    _collect_duplicates(_as_list(model.get("reasoning_paths")), "path_id", "path", duplicates)
    for path in _as_list(model.get("reasoning_paths")):
        if isinstance(path, dict):
            _collect_duplicates(_as_list(path.get("steps")), "step_id", f"step:{path.get('path_id')}", duplicates)
    _collect_duplicates(_as_list(model.get("knowledge_emissions")), "knowledge_id", "knowledge", duplicates)
    return sorted(duplicates)


def _collect_duplicates(items: list[Any], key: str, label: str, duplicates: list[str]) -> None:
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not item.get(key):
            continue
        value = str(item[key])
        if value in seen:
            duplicates.append(f"{label}:{value}")
        seen.add(value)


def _input_relations_valid(model: dict[str, Any]) -> bool:
    input_state = model.get("input_state")
    if not isinstance(input_state, dict):
        return False
    unit_ids = {unit.get("unit_id") for unit in _as_list(input_state.get("units")) if isinstance(unit, dict)}
    for relation in _as_list(input_state.get("relations")):
        if not isinstance(relation, dict):
            continue
        if relation.get("source") not in unit_ids or relation.get("target") not in unit_ids:
            return False
    return True


def _step_signature(step: dict[str, Any]) -> str:
    return "|".join(str(step.get(field, "")) for field in ("source", "operation", "target"))


def _branch_decisions(model: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = []
    metadata = model.get("metadata")
    if isinstance(metadata, dict):
        decisions.extend([item for item in _as_list(metadata.get("branch_decisions")) if isinstance(item, dict)])
    for path in _as_list(model.get("reasoning_paths")):
        if isinstance(path, dict) and isinstance(path.get("metadata"), dict):
            decisions.extend([item for item in _as_list(path["metadata"].get("branch_decisions")) if isinstance(item, dict)])
    return decisions


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return _canonicalize_dict(value)
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _canonicalize_dict(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") == CONTRACT_SCHEMA:
        ordered = _reorder(value, TOP_LEVEL_ORDER)
        ordered["model_ref"] = _reorder(_canonicalize(value.get("model_ref", {})), MODEL_REF_ORDER)
        ordered["evaluation_target_ref"] = _reorder(_canonicalize(value.get("evaluation_target_ref", {})), TARGET_REF_ORDER)
        ordered["summary"] = _reorder(_canonicalize(value.get("summary", {})), SUMMARY_ORDER)
        ordered["checks"] = _sort_checks([
            _reorder(_canonicalize(item), CHECK_ORDER) for item in _as_list(value.get("checks"))
        ])
        ordered["diagnostics"] = _sort_diagnostics([
            _reorder(_canonicalize(item), DIAGNOSTIC_ORDER) for item in _as_list(value.get("diagnostics"))
        ])
        if "metadata" not in value or not value.get("metadata"):
            ordered.pop("metadata", None)
        return ordered
    return {key: _canonicalize(value[key]) for key in sorted(value)}


def _reorder(value: dict[str, Any], order: tuple[str, ...]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in order:
        if key in value:
            ordered[key] = value[key]
    for key in sorted(value):
        if key not in ordered:
            ordered[key] = value[key]
    return ordered


def _sort_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {check_type: index for index, check_type in enumerate(CHECK_TYPES)}
    return sorted(checks, key=lambda check: (order.get(str(check.get("check_type")), len(order)), str(check.get("check_id", ""))))


def _sort_diagnostics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (str(item.get("code", "")), str(item.get("location", "")), str(item.get("message", ""))))


def _diag(code: str, message: str, *, severity: str = "error", location: str | None = None) -> dict[str, Any]:
    diagnostic = {"code": code, "severity": severity, "message": message}
    if location is not None:
        diagnostic["location"] = location
    return diagnostic


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
