"""Tests for reasonscript-phase8-golden-validation/1.0."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from toolchain.ci import COMPATIBILITY_TARGETS, run_pipeline
from toolchain.phase8_golden_validation import CONTRACT_SCHEMA, SCENARIOS, VALID_SCENARIOS, validate_phase8_golden
from toolchain.reasoning_evaluation_report import serialize_evaluation_report, validate_evaluation_report
from toolchain.reasoning_model_contract import serialize_reasoning_model, validate as validate_reasoning_model
from toolchain.reasoning_runtime import run_reasoning_runtime, serialize_reasoning_runtime_result, validate_reasoning_runtime_result


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "v0_8" / "reasoning_runtime"
GOLDEN = ROOT / "tests" / "fixtures" / "golden" / "phase8"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_gv_t001_required_source_fixtures_exist() -> None:
    for scenario in SCENARIOS:
        assert (EXAMPLES / f"{scenario}.rsn").is_file()


def test_gv_t002_required_golden_artifacts_exist() -> None:
    for scenario in SCENARIOS:
        assert (GOLDEN / scenario).is_dir()
        assert (GOLDEN / scenario / "reasoning_runtime_result.json").is_file()
    for scenario in VALID_SCENARIOS:
        assert (GOLDEN / scenario / "reasoning_model.json").is_file()
        assert (GOLDEN / scenario / "reasoning_evaluation_report.json").is_file()


def test_gv_t101_golden_artifacts_validate_against_phase8_contracts() -> None:
    for scenario in VALID_SCENARIOS:
        assert validate_reasoning_model(GOLDEN / scenario / "reasoning_model.json")["valid"] is True
        assert validate_evaluation_report(GOLDEN / scenario / "reasoning_evaluation_report.json")["valid"] is True
    for scenario in SCENARIOS:
        assert validate_reasoning_runtime_result(GOLDEN / scenario / "reasoning_runtime_result.json")["valid"] is True


def test_gv_t201_generated_artifacts_match_golden() -> None:
    for scenario in SCENARIOS:
        runtime = run_reasoning_runtime(EXAMPLES / f"{scenario}.rsn")
        assert serialize_reasoning_runtime_result(runtime) == (GOLDEN / scenario / "reasoning_runtime_result.json").read_text(encoding="utf-8")
        if scenario in VALID_SCENARIOS:
            assert serialize_reasoning_model(runtime["reasoning_model"]) == (GOLDEN / scenario / "reasoning_model.json").read_text(encoding="utf-8")
            assert serialize_evaluation_report(runtime["evaluation_report"]) == (
                GOLDEN / scenario / "reasoning_evaluation_report.json"
            ).read_text(encoding="utf-8")


def test_gv_t205_unreachable_goal_is_a_valid_failed_evaluation() -> None:
    report = _load(GOLDEN / "unreachable_goal" / "reasoning_evaluation_report.json")
    reachability = next(check for check in report["checks"] if check["check_type"] == "reachability")
    assert report["summary"]["status"] == "failed"
    assert reachability["status"] == "failed"


def test_gv_t204_branch_selection_includes_branch_traceability() -> None:
    report = _load(GOLDEN / "branch_selection" / "reasoning_evaluation_report.json")
    assert "branch_traceability" in report["evaluation_target_ref"]["required_checks"]
    assert any(check["check_type"] == "branch_traceability" and check["status"] == "passed" for check in report["checks"])


def test_gv_t301_phase8_generation_and_serialization_are_stable() -> None:
    for scenario in SCENARIOS:
        source = EXAMPLES / f"{scenario}.rsn"
        first = run_reasoning_runtime(source)
        second = run_reasoning_runtime(source)
        assert serialize_reasoning_runtime_result(first) == serialize_reasoning_runtime_result(second)
        if scenario in VALID_SCENARIOS:
            assert serialize_reasoning_model(first["reasoning_model"]) == serialize_reasoning_model(json.loads(serialize_reasoning_model(first["reasoning_model"])))
            assert serialize_evaluation_report(first["evaluation_report"]) == serialize_evaluation_report(json.loads(serialize_evaluation_report(first["evaluation_report"])))


def test_gv_t305_cli_json_output_is_stable() -> None:
    source = "examples/v0_8/reasoning_runtime/branch_selection.rsn"
    first = subprocess.run([sys.executable, "-m", "toolchain", "reasoning-runtime", "run", source, "--json"], cwd=ROOT, text=True, capture_output=True, check=False)
    second = subprocess.run([sys.executable, "-m", "toolchain", "reasoning-runtime", "run", source, "--json"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_gv_t401_phase8_compatibility_target_is_registered() -> None:
    assert CONTRACT_SCHEMA in COMPATIBILITY_TARGETS
    assert COMPATIBILITY_TARGETS[CONTRACT_SCHEMA]() is True


def test_gv_t402_phase8_validation_passes_and_ci_includes_it() -> None:
    assert validate_phase8_golden(ROOT)["ok"] is True
    result = run_pipeline(ROOT, run_tests=False)
    golden_phase = next(phase for phase in result["phases"] if phase["id"] == "golden")
    assert golden_phase["status"] == "PASS"
    assert golden_phase["metadata"]["phase8_golden_validation"]["target"] == CONTRACT_SCHEMA
