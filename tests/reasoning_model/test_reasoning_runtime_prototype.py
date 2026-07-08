"""Tests for reasonscript-reasoning-runtime-prototype/1.0 (Phase 8C)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.reason_cli import _analyze_result
from toolchain.reasoning_model_contract import validate as validate_reasoning_model
from toolchain.reasoning_runtime import (
    CONTRACT_SCHEMA,
    evaluate_generated_reasoning_model,
    run_reasoning_runtime,
    serialize_reasoning_runtime_result,
    validate_reasoning_runtime_result,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "reasoning_runtime"
EXAMPLES = ROOT / "examples" / "v0_8" / "reasoning_runtime"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _codes(result: dict) -> set[str]:
    return {item["code"] for item in result["diagnostics"]}


def _valid_result() -> dict:
    return run_reasoning_runtime(EXAMPLES / "calculation_chain.rsn")


def test_rrp_t001_minimal_valid_runtime_result_passes() -> None:
    result = validate_reasoning_runtime_result(_load("valid_minimal.json"))
    assert result["valid"] is True


def test_rrp_t002_valid_runtime_result_with_full_nested_reasoning_model_passes() -> None:
    runtime = _valid_result()
    assert validate_reasoning_model(runtime["reasoning_model"])["valid"] is True
    assert validate_reasoning_runtime_result(runtime)["valid"] is True


def test_rrp_t003_valid_runtime_result_with_full_nested_evaluation_report_passes() -> None:
    runtime = _valid_result()
    assert runtime["evaluation_report"]["summary"]["passed"] is True
    assert validate_reasoning_runtime_result(runtime)["valid"] is True


def test_rrp_t004_runtime_result_serializes_deterministically() -> None:
    runtime = _valid_result()
    shuffled = {
        "diagnostics": runtime["diagnostics"],
        "evaluation_report": runtime["evaluation_report"],
        "reasoning_model": runtime["reasoning_model"],
        "pipeline_status": runtime["pipeline_status"],
        "source_ref": runtime["source_ref"],
        "run_id": runtime["run_id"],
        "schema_version": runtime["schema_version"],
    }
    assert serialize_reasoning_runtime_result(runtime) == serialize_reasoning_runtime_result(shuffled)
    assert serialize_reasoning_runtime_result(runtime) == serialize_reasoning_runtime_result(_valid_result())


def test_rrp_t101_missing_schema_version_fails() -> None:
    result = _valid_result()
    del result["schema_version"]
    assert "RRP-001" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t102_unsupported_schema_version_fails() -> None:
    result = _valid_result()
    result["schema_version"] = "reasonscript-reasoning-runtime-prototype/9.9"
    assert "RRP-002" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t103_missing_run_id_fails() -> None:
    assert "RRP-003" in _codes(validate_reasoning_runtime_result(_load("invalid_missing_run_id.json")))


def test_rrp_t104_missing_source_ref_fails() -> None:
    result = _valid_result()
    del result["source_ref"]
    assert "RRP-004" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t105_missing_pipeline_status_fails() -> None:
    result = _valid_result()
    del result["pipeline_status"]
    assert "RRP-005" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t106_missing_reasoning_model_fails() -> None:
    result = _valid_result()
    del result["reasoning_model"]
    assert "RRP-006" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t107_missing_evaluation_report_fails() -> None:
    result = _valid_result()
    del result["evaluation_report"]
    assert "RRP-007" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t108_missing_diagnostics_fails() -> None:
    result = _valid_result()
    del result["diagnostics"]
    assert "RRP-008" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t109_invalid_pipeline_status_fails() -> None:
    result = _valid_result()
    result["pipeline_status"]["status"] = "unknown"
    assert "RRP-PIPE-STATUS" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t110_pipeline_status_inconsistent_with_artifact_availability_fails() -> None:
    result = _valid_result()
    result["pipeline_status"]["execution_plan_available"] = False
    assert "RRP-PIPE-INCONSISTENT" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t111_nested_reasoning_model_validation_failure_is_reported() -> None:
    result = _valid_result()
    del result["reasoning_model"]["model_id"]
    assert "RRP-PROJ-007" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t112_nested_evaluation_report_validation_failure_is_reported() -> None:
    result = _valid_result()
    del result["evaluation_report"]["report_id"]
    assert "RRP-EVAL-002" in _codes(validate_reasoning_runtime_result(result))


def test_rrp_t201_object_relation_like_source_projects_to_input_state_units_and_relations() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "animal_isa.rsn")
    input_state = runtime["reasoning_model"]["input_state"]
    assert input_state["units"]
    assert input_state["relations"]


def test_rrp_t202_calculation_chain_projects_to_reasoning_steps() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "calculation_chain.rsn")
    steps = runtime["reasoning_model"]["reasoning_paths"][0]["steps"]
    assert any(step["step_type"] == "calculation" for step in steps)


def test_rrp_t203_function_return_projects_to_function_return_step() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "function_return.rsn")
    steps = runtime["reasoning_model"]["reasoning_paths"][0]["steps"]
    assert any(step["step_type"] == "function_return" for step in steps)


def test_rrp_t204_branch_selection_projects_to_branch_selection_step() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "branch_selection.rsn")
    steps = runtime["reasoning_model"]["reasoning_paths"][0]["steps"]
    assert any(step["step_type"] == "branch_selection" for step in steps)


def test_rrp_t205_knowledge_artifact_projects_to_knowledge_emission() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "function_return.rsn")
    assert runtime["reasoning_model"]["knowledge_emissions"]


def test_rrp_t206_execution_plan_goal_projects_to_evaluation_target() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "function_return.rsn")
    assert runtime["reasoning_model"]["evaluation_target"]["goal"] == "Answer.state.result"


def test_rrp_t207_missing_execution_plan_emits_rrp_pipe_003() -> None:
    result = run_reasoning_runtime(_load("invalid_missing_execution_plan.json"))
    assert result["pipeline_status"]["status"] == "failed"
    assert "RRP-PIPE-003" in {item["code"] for item in result["diagnostics"]}


def test_rrp_t208_missing_knowledge_emits_warning_or_partial_status() -> None:
    bundle = _analyze_result(EXAMPLES / "calculation_chain.rsn", "normal")
    del bundle["artifacts"]["knowledge"]
    result = run_reasoning_runtime(bundle)
    assert result["pipeline_status"]["status"] == "partial"
    assert "RRP-PIPE-005" in {item["code"] for item in result["diagnostics"]}


def test_rrp_t301_animal_isa_source_produces_valid_runtime_result() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "animal_isa.rsn")
    assert validate_reasoning_runtime_result(runtime)["valid"] is True


def test_rrp_t302_calculation_chain_source_produces_valid_runtime_result() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "calculation_chain.rsn")
    assert validate_reasoning_runtime_result(runtime)["valid"] is True


def test_rrp_t303_branch_selection_source_produces_valid_runtime_result() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "branch_selection.rsn")
    assert validate_reasoning_runtime_result(runtime)["valid"] is True


def test_rrp_t304_unreachable_goal_model_produces_valid_failed_evaluation_report() -> None:
    model = copy.deepcopy(run_reasoning_runtime(EXAMPLES / "calculation_chain.rsn")["reasoning_model"])
    model["evaluation_target"]["goal"] = "Unreachable.state"
    model["evaluation_target"]["expected_relation"] = {
        "relation": "ResultTransition",
        "source": "MissingStart",
        "target": "Unreachable.state",
    }
    report = evaluate_generated_reasoning_model(model)
    assert report["summary"]["passed"] is False


def test_rrp_t305_invalid_source_produces_fatal_runtime_result() -> None:
    runtime = run_reasoning_runtime(EXAMPLES / "invalid_parse.rsn")
    assert runtime["pipeline_status"]["status"] == "fatal"
    assert "RRP-PIPE-001" in {item["code"] for item in runtime["diagnostics"]}


def test_rrp_t306_runtime_output_is_deterministic() -> None:
    first = serialize_reasoning_runtime_result(run_reasoning_runtime(EXAMPLES / "branch_selection.rsn"))
    second = serialize_reasoning_runtime_result(run_reasoning_runtime(EXAMPLES / "branch_selection.rsn"))
    assert first == second


def test_contract_schema_constant_matches_specification() -> None:
    assert CONTRACT_SCHEMA == "reasonscript-reasoning-runtime-prototype/1.0"
