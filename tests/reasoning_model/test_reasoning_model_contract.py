"""Tests for reasonscript-reasoning-model/1.0 (Phase 8A)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from toolchain.reasoning_model_contract import (
    CONTRACT_SCHEMA,
    VALIDATOR_SCHEMA,
    serialize_reasoning_model,
    validate,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "reasoning_model"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _valid_model() -> dict:
    return copy.deepcopy(_load("valid_minimal.json"))


def _codes(result: dict) -> set[str]:
    return {item["code"] for item in result["diagnostics"]}


# --- RM-T001..T004: valid cases -------------------------------------------------


def test_rm_t001_minimal_valid_model_passes() -> None:
    result = validate(_valid_model())
    assert result["schema_version"] == VALIDATOR_SCHEMA
    assert result["valid"] is True
    assert result["diagnostics"] == []


def test_rm_t002_valid_model_with_artifact_refs_passes() -> None:
    model = _valid_model()
    assert model["source_ref"]["artifact_refs"] == {
        "reason_ir": "reason_ir.json",
        "execution_plan": "execution_plan.json",
        "simulation": "simulation.json",
        "knowledge": "knowledge.json",
    }
    result = validate(model)
    assert result["valid"] is True


def test_rm_t003_valid_model_with_empty_diagnostics_passes() -> None:
    model = _valid_model()
    model["diagnostics"] = []
    result = validate(model)
    assert result["valid"] is True
    assert result["diagnostics"] == []


def test_rm_t004_valid_model_serializes_deterministically() -> None:
    model = _valid_model()
    shuffled = {
        "diagnostics": model["diagnostics"],
        "evaluation_target": model["evaluation_target"],
        "knowledge_emissions": model["knowledge_emissions"],
        "selected_path_id": model["selected_path_id"],
        "reasoning_paths": model["reasoning_paths"],
        "input_state": model["input_state"],
        "source_ref": model["source_ref"],
        "model_id": model["model_id"],
        "schema_version": model["schema_version"],
    }
    first = serialize_reasoning_model(model)
    second = serialize_reasoning_model(shuffled)
    assert first == second
    assert serialize_reasoning_model(model) == serialize_reasoning_model(_valid_model())
    assert list(json.loads(first).keys())[0] == "schema_version"


# --- RM-T101..T117: invalid cases -----------------------------------------------


def test_rm_t101_missing_schema_version_fails() -> None:
    model = _valid_model()
    del model["schema_version"]
    result = validate(model)
    assert result["valid"] is False
    assert "RM-001" in _codes(result)


def test_rm_t102_unsupported_schema_version_fails() -> None:
    model = _valid_model()
    model["schema_version"] = "reasonscript-reasoning-model/9.9"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-002" in _codes(result)


def test_rm_t103_missing_model_id_fails() -> None:
    result = validate(_load("invalid_missing_model_id.json"))
    assert result["valid"] is False
    assert "RM-003" in _codes(result)


def test_rm_t104_missing_source_ref_fails() -> None:
    model = _valid_model()
    del model["source_ref"]
    result = validate(model)
    assert result["valid"] is False
    assert "RM-005" in _codes(result)


def test_rm_t105_missing_input_state_fails() -> None:
    model = _valid_model()
    del model["input_state"]
    result = validate(model)
    assert result["valid"] is False
    assert "RM-006" in _codes(result)


def test_rm_t106_duplicate_input_unit_id_fails() -> None:
    model = _valid_model()
    model["input_state"]["units"].append({"unit_id": "Dog", "unit_type": "object", "value": "Dog"})
    result = validate(model)
    assert result["valid"] is False
    assert "RM-IN-004" in _codes(result)


def test_rm_t107_relation_source_missing_fails() -> None:
    model = _valid_model()
    model["input_state"]["relations"][0]["source"] = "Cat"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-IN-006" in _codes(result)


def test_rm_t108_relation_target_missing_fails() -> None:
    model = _valid_model()
    model["input_state"]["relations"][0]["target"] = "Plant"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-IN-007" in _codes(result)


def test_rm_t109_missing_reasoning_paths_fails() -> None:
    model = _valid_model()
    del model["reasoning_paths"]
    result = validate(model)
    assert result["valid"] is False
    assert "RM-007" in _codes(result)


def test_rm_t110_duplicate_path_id_fails() -> None:
    model = _valid_model()
    duplicate = copy.deepcopy(model["reasoning_paths"][0])
    duplicate["status"] = "candidate"
    model["reasoning_paths"].append(duplicate)
    result = validate(model)
    assert result["valid"] is False
    assert "RM-PATH-001" in _codes(result)


def test_rm_t111_selected_path_id_missing_target_fails() -> None:
    model = _valid_model()
    model["selected_path_id"] = "path_unknown"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-009" in _codes(result)


def test_rm_t112_duplicate_step_id_fails() -> None:
    result = validate(_load("invalid_duplicate_step_id.json"))
    assert result["valid"] is False
    assert "RM-STEP-001" in _codes(result)


def test_rm_t113_invalid_step_type_fails() -> None:
    model = _valid_model()
    model["reasoning_paths"][0]["steps"][0]["step_type"] = "not_a_step_type"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-STEP-002" in _codes(result)


def test_rm_t114_duplicate_knowledge_id_fails() -> None:
    model = _valid_model()
    duplicate = copy.deepcopy(model["knowledge_emissions"][0])
    model["knowledge_emissions"].append(duplicate)
    result = validate(model)
    assert result["valid"] is False
    assert "RM-KNOW-001" in _codes(result)


def test_rm_t115_knowledge_source_step_id_missing_target_fails() -> None:
    model = _valid_model()
    model["knowledge_emissions"][0]["source_step_id"] = "step_unknown"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-KNOW-002" in _codes(result)


def test_rm_t116_missing_evaluation_target_fails() -> None:
    model = _valid_model()
    del model["evaluation_target"]
    result = validate(model)
    assert result["valid"] is False
    assert "RM-010" in _codes(result)


def test_rm_t117_invalid_required_check_fails() -> None:
    model = _valid_model()
    model["evaluation_target"]["required_checks"] = ["not_a_check"]
    result = validate(model)
    assert result["valid"] is False
    assert "RM-EVAL-004" in _codes(result)


# --- Additional contract behavior -----------------------------------------------


def test_contract_schema_constant_matches_specification() -> None:
    assert CONTRACT_SCHEMA == "reasonscript-reasoning-model/1.0"


def test_validate_accepts_file_path() -> None:
    result = validate(FIXTURES / "valid_minimal.json")
    assert result["valid"] is True


def test_no_selected_path_fails() -> None:
    model = _valid_model()
    model["reasoning_paths"][0]["status"] = "candidate"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-PATH-005" in _codes(result)


def test_multiple_selected_paths_fails() -> None:
    model = _valid_model()
    second = copy.deepcopy(model["reasoning_paths"][0])
    second["path_id"] = "path_alt"
    second["path_signature"] = "Dog.IsA.Mammal"
    model["reasoning_paths"].append(second)
    result = validate(model)
    assert result["valid"] is False
    assert "RM-PATH-006" in _codes(result)


def test_missing_evidence_refs_fails() -> None:
    model = _valid_model()
    del model["reasoning_paths"][0]["steps"][0]["evidence_refs"]
    result = validate(model)
    assert result["valid"] is False
    assert "RM-STEP-006" in _codes(result)


def test_empty_evidence_path_in_successful_model_fails() -> None:
    model = _valid_model()
    model["knowledge_emissions"][0]["evidence_path"] = []
    result = validate(model)
    assert result["valid"] is False
    assert "RM-KNOW-003" in _codes(result)


def test_unsupported_input_kind_is_diagnosed() -> None:
    model = _valid_model()
    model["input_state"]["input_kind"] = "not_a_kind"
    result = validate(model)
    assert result["valid"] is False
    assert "RM-IN-003" in _codes(result)
