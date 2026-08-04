"""Tests for reasonscript-reasoning-evaluation-report/1.0 (Phase 8B)."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from toolchain.reasoning_evaluation_report import (
    CONTRACT_SCHEMA,
    VALIDATOR_SCHEMA,
    evaluate_reasoning_model,
    serialize_evaluation_report,
    validate_evaluation_report,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT_FIXTURES = ROOT / "tests" / "fixtures" / "reasoning_evaluation_report"
MODEL_FIXTURES = ROOT / "tests" / "fixtures" / "reasoning_model"


def _load_report(name: str) -> dict:
    return json.loads((REPORT_FIXTURES / name).read_text(encoding="utf-8"))


def _valid_report() -> dict:
    return copy.deepcopy(_load_report("valid_minimal.json"))


def _valid_model() -> dict:
    return json.loads((MODEL_FIXTURES / "valid_minimal.json").read_text(encoding="utf-8"))


def _codes(result: dict) -> set[str]:
    return {item["code"] for item in result["diagnostics"]}


def _check(report: dict, check_type: str) -> dict:
    return next(item for item in report["checks"] if item["check_type"] == check_type)


def test_er_t001_minimal_valid_evaluation_report_passes() -> None:
    result = validate_evaluation_report(_valid_report())
    assert result["schema_version"] == VALIDATOR_SCHEMA
    assert result["valid"] is True
    assert result["diagnostics"] == []


def test_er_t002_valid_report_with_all_required_checks_passes() -> None:
    report = evaluate_reasoning_model(_valid_model())
    result = validate_evaluation_report(report)
    assert result["valid"] is True
    assert [check["check_type"] for check in report["checks"]] == [
        "reachability",
        "determinism",
        "evidence_completeness",
        "consistency",
    ]


def test_er_t003_valid_failed_report_passes_contract_validation() -> None:
    result = validate_evaluation_report(_load_report("valid_failed_reachability.json"))
    assert result["valid"] is True


def test_er_t004_valid_warning_report_passes_contract_validation() -> None:
    report = _valid_report()
    report["summary"]["status"] = "warning"
    report["summary"]["passed"] = False
    report["summary"]["total_checks"] = 2
    report["summary"]["warning_checks"] = 1
    report["checks"].append({
        "check_id": "check_minimality",
        "check_type": "minimality",
        "required": False,
        "status": "warning",
        "passed": False,
        "message": "Selected path contains an unreferenced step.",
        "evidence_refs": [],
        "details": {},
    })
    result = validate_evaluation_report(report)
    assert result["valid"] is True


def test_er_t005_deterministic_report_serialization_is_stable() -> None:
    report = evaluate_reasoning_model(_valid_model())
    shuffled = {
        "diagnostics": report["diagnostics"],
        "checks": list(reversed(report["checks"])),
        "summary": report["summary"],
        "evaluation_target_ref": report["evaluation_target_ref"],
        "model_ref": report["model_ref"],
        "report_id": report["report_id"],
        "schema_version": report["schema_version"],
    }
    first = serialize_evaluation_report(report)
    second = serialize_evaluation_report(shuffled)
    assert first == second
    assert list(json.loads(first).keys())[0] == "schema_version"


def test_er_t101_missing_schema_version_fails() -> None:
    report = _valid_report()
    del report["schema_version"]
    assert "ER-001" in _codes(validate_evaluation_report(report))


def test_er_t102_unsupported_schema_version_fails() -> None:
    report = _valid_report()
    report["schema_version"] = "reasonscript-reasoning-evaluation-report/9.9"
    assert "ER-002" in _codes(validate_evaluation_report(report))


def test_er_t103_missing_report_id_fails() -> None:
    assert "ER-003" in _codes(validate_evaluation_report(_load_report("invalid_missing_report_id.json")))


def test_er_t104_missing_model_ref_fails() -> None:
    report = _valid_report()
    del report["model_ref"]
    assert "ER-004" in _codes(validate_evaluation_report(report))


def test_er_t105_missing_evaluation_target_ref_fails() -> None:
    report = _valid_report()
    del report["evaluation_target_ref"]
    assert "ER-005" in _codes(validate_evaluation_report(report))


def test_er_t106_missing_summary_fails() -> None:
    report = _valid_report()
    del report["summary"]
    assert "ER-006" in _codes(validate_evaluation_report(report))


def test_er_t107_missing_checks_fails() -> None:
    report = _valid_report()
    del report["checks"]
    assert "ER-007" in _codes(validate_evaluation_report(report))


def test_er_t108_missing_diagnostics_fails() -> None:
    report = _valid_report()
    del report["diagnostics"]
    assert "ER-008" in _codes(validate_evaluation_report(report))


def test_er_t109_unsupported_model_schema_version_fails() -> None:
    report = _valid_report()
    report["model_ref"]["model_schema_version"] = "reasonscript-reasoning-model/9.9"
    assert "ER-MODEL-003" in _codes(validate_evaluation_report(report))


def test_er_t110_invalid_required_check_fails() -> None:
    report = _valid_report()
    report["evaluation_target_ref"]["required_checks"] = ["not_a_check"]
    assert "ER-TARGET-004" in _codes(validate_evaluation_report(report))


def test_er_t111_duplicate_check_id_fails() -> None:
    report = _valid_report()
    report["checks"].append(copy.deepcopy(report["checks"][0]))
    report["summary"]["total_checks"] = 2
    report["summary"]["passed_checks"] = 2
    assert "ER-CHECK-001" in _codes(validate_evaluation_report(report))


def test_er_t112_invalid_check_type_fails() -> None:
    report = _valid_report()
    report["checks"][0]["check_type"] = "not_a_check"
    assert "ER-CHECK-003" in _codes(validate_evaluation_report(report))


def test_er_t113_invalid_check_status_fails() -> None:
    report = _valid_report()
    report["checks"][0]["status"] = "not_a_status"
    assert "ER-CHECK-005" in _codes(validate_evaluation_report(report))


def test_er_t114_passed_flag_inconsistent_with_check_status_fails() -> None:
    report = _valid_report()
    report["checks"][0]["passed"] = False
    assert "ER-CHECK-007" in _codes(validate_evaluation_report(report))


def test_er_t115_missing_required_check_result_fails() -> None:
    assert "ER-CHECK-008" in _codes(validate_evaluation_report(_load_report("invalid_missing_required_check.json")))


def test_er_t116_required_check_skipped_without_fatal_diagnostic_fails() -> None:
    report = _valid_report()
    report["checks"][0]["status"] = "skipped"
    report["checks"][0]["passed"] = False
    report["summary"]["status"] = "failed"
    report["summary"]["passed"] = False
    report["summary"]["required_checks_passed"] = False
    assert "ER-CHECK-009" in _codes(validate_evaluation_report(report))


def test_er_t117_summary_counts_inconsistent_with_checks_fails() -> None:
    report = _valid_report()
    report["summary"]["total_checks"] = 99
    assert "ER-SUM-005" in _codes(validate_evaluation_report(report))


def test_er_t118_summary_status_inconsistent_with_checks_fails() -> None:
    assert "ER-SUM-006" in _codes(validate_evaluation_report(_load_report("invalid_inconsistent_summary.json")))


def test_er_t201_evaluator_produces_passed_report_for_valid_animal_reasoner_model() -> None:
    report = evaluate_reasoning_model(_valid_model())
    assert report["schema_version"] == CONTRACT_SCHEMA
    assert report["summary"]["status"] == "passed"
    assert report["summary"]["passed"] is True
    assert validate_evaluation_report(report)["valid"] is True


def test_er_t202_evaluator_fails_reachability_when_goal_is_unreachable() -> None:
    model = _valid_model()
    model["evaluation_target"]["goal"] = "Plant"
    del model["evaluation_target"]["expected_relation"]
    report = evaluate_reasoning_model(model)
    assert _check(report, "reachability")["status"] == "failed"


def test_er_t203_evaluator_fails_evidence_completeness_when_knowledge_evidence_path_is_empty() -> None:
    model = _valid_model()
    model["knowledge_emissions"][0]["evidence_path"] = []
    report = evaluate_reasoning_model(model)
    assert _check(report, "evidence_completeness")["status"] == "failed"


def test_er_t204_evaluator_fails_consistency_when_selected_path_id_is_invalid() -> None:
    model = _valid_model()
    model["selected_path_id"] = "path_missing"
    report = evaluate_reasoning_model(model)
    assert _check(report, "consistency")["status"] == "failed"


def test_er_t205_evaluator_reports_determinism_failure_on_duplicate_ids() -> None:
    model = _valid_model()
    model["reasoning_paths"].append(copy.deepcopy(model["reasoning_paths"][0]))
    report = evaluate_reasoning_model(model)
    assert _check(report, "determinism")["status"] == "failed"


def test_er_t206_evaluator_emits_one_check_result_per_required_check() -> None:
    model = _valid_model()
    model["evaluation_target"]["required_checks"] = [
        "reachability",
        "determinism",
        "evidence_completeness",
        "consistency",
        "minimality",
        "branch_traceability",
    ]
    report = evaluate_reasoning_model(model)
    assert [check["check_type"] for check in report["checks"]] == model["evaluation_target"]["required_checks"]


def test_er_t207_evaluator_rejects_invalid_reasoning_model_artifact() -> None:
    model = _valid_model()
    del model["model_id"]
    report = evaluate_reasoning_model(model)
    assert report["summary"]["status"] == "fatal"
    assert "ER-EVAL-001" in {item["code"] for item in report["diagnostics"]}


def test_er_t208_evaluator_output_is_deterministic() -> None:
    model = _valid_model()
    assert serialize_evaluation_report(evaluate_reasoning_model(model)) == serialize_evaluation_report(evaluate_reasoning_model(model))


def test_cli_evaluate_and_validate_json() -> None:
    model_path = MODEL_FIXTURES / "valid_minimal.json"
    evaluate = subprocess.run(
        [str(ROOT / "reason"), "reasoning-eval", "evaluate", str(model_path), "--json"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert evaluate.returncode == 0
    report = json.loads(evaluate.stdout)
    assert report["schema_version"] == CONTRACT_SCHEMA

    report_path = REPORT_FIXTURES / "valid_minimal.json"
    validate = subprocess.run(
        [str(ROOT / "reason"), "reasoning-eval", "validate", str(report_path), "--json"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert validate.returncode == 0
    assert json.loads(validate.stdout)["valid"] is True
