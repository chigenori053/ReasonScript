from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from toolchain.reasonunit_object import (
    CANONICAL_ARTIFACTS,
    ObjectTransaction,
    canonical_digest,
    canonicalize,
    dependency_closure,
    generate_execution_projection,
    generate_universal_model,
    projection_is_current,
    query_object,
    validate_object,
    validate_universal_model,
    verify_ruo_c1,
)
from toolchain.reasonunit_object.universal import PROFILE, reference_object

ROOT = Path(__file__).resolve().parents[2]

def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "ruo-u1"
    assert generate_universal_model(ROOT, output)["phase_status"] == "VALIDATED"
    return output

def test_c0_c1_prerequisites_and_count_reconciliation(tmp_path: Path) -> None:
    verified = verify_ruo_c1(ROOT)
    assert verified["ok"] and verified["summary"] == {"passed": 56, "failed": 0, "total": 56}
    assert verified["count_reconciliation"]["authoritative_aggregate"] == 96
    assert verified["count_reconciliation"]["focused_regression_suite"] == 83
    missing = tmp_path / "missing"; missing.mkdir()
    assert not generate_universal_model(ROOT, tmp_path / "output", c1_directory=missing)["phase_status"] == "VALIDATED"

def test_generates_exactly_38_schema_versioned_artifacts(generated: Path) -> None:
    assert {path.name for path in generated.iterdir()} == set(CANONICAL_ARTIFACTS)
    manifest = read(generated / "run_manifest.json")["data"]
    assert manifest["artifact_count"] == len(manifest["artifacts"]) == 38
    for path in generated.glob("*.json"):
        value = read(path)
        assert value["profile_version"] == PROFILE
        assert set(value) == {"schema_version", "profile_version", "data"}

def test_matrix_is_t001_through_t065(generated: Path) -> None:
    data = read(generated / "validation_summary.json")["data"]
    assert [item["test_id"] for item in data["tests"]] == [f"RUO-U1-T{i:03}" for i in range(1, 66)]
    assert data["summary"] == {"passed": 65, "failed": 0, "total": 65}
    assert data["statuses"]["phase_status"] == "VALIDATED"
    assert data["statuses"]["transition_decision"] == "PROCEED_TO_RUO-F1"

def test_reference_object_is_valid_and_registry_reordering_is_semantically_stable() -> None:
    value = reference_object()
    assert validate_object(value) == []
    reordered = copy.deepcopy(value); reordered["units"].reverse(); reordered["payloads"].reverse()
    assert canonical_digest(reordered) == canonical_digest(value)
    with pytest.raises(ValueError): canonicalize({"invalid": math.inf})

def test_identity_ownership_containment_and_atomic_contracts() -> None:
    value = reference_object(); value["units"].append(copy.deepcopy(value["units"][0]))
    assert "RUO-U1-004" in {item["code"] for item in validate_object(value)}
    value = reference_object(); value["units"][1]["owner_object_id"] = "ruo:object:other"
    assert "RUO-U1-005" in {item["code"] for item in validate_object(value)}
    value = reference_object(); value["units"][1]["children"] = ["ruo:unit:root"]
    assert {"RUO-U1-003", "RUO-U1-006"}.issubset({item["code"] for item in validate_object(value)})

def test_all_payload_profiles_and_profile_specific_failures() -> None:
    registry = read(ROOT / "artifacts/reasonunit_object/ruo_u1/payload_profile_registry.json")["data"] if (ROOT / "artifacts/reasonunit_object/ruo_u1/payload_profile_registry.json").is_file() else None
    if registry: assert registry["count"] == 9
    value = reference_object(); value["payloads"][0]["value"].pop("offset_indexing")
    assert "RUO-U1-008" in {item["code"] for item in validate_object(value)}
    value = reference_object(); value["payloads"][1]["value"].pop("reference_frame")
    assert "RUO-U1-009" in {item["code"] for item in validate_object(value)}
    value = reference_object(); value["payloads"][0]["profile_id"] = "project.unknown/1"
    assert "RUO-U1-007" in {item["code"] for item in validate_object(value)}

def test_relations_evidence_state_dependencies_and_extensions() -> None:
    value = reference_object(); value["relations"][0]["target_id"] = "ruo:payload:missing"
    assert "RUO-U1-011" in {item["code"] for item in validate_object(value)}
    value = reference_object(); value["evidence_registry"][0].pop("confidence_contract")
    assert "RUO-U1-012" in {item["code"] for item in validate_object(value)}
    value = reference_object(); value["extensions"] = {"unknown": {"critical": True}}
    assert "RUO-U1-019" in {item["code"] for item in validate_object(value)}
    value = reference_object(); value["dependency_graph"].append({"source_id": "ruo:payload:numeric", "target_id": "ruo:state:committed"})
    assert "RUO-U1-013" in {item["code"] for item in validate_object(value)}
    assert dependency_closure(reference_object(), ["ruo:payload:numeric"]) == ["ruo:payload:numeric", "ruo:state:committed"]

def test_transactions_are_atomic_and_projection_is_derived_and_stale_checked() -> None:
    value = reference_object(); before = canonical_digest(value)
    invalid = ObjectTransaction(value).commit({"state_updates": {"ruo:state:missing": 1}}, source_revision="ruo:revision:0", transaction_id="ruo:transaction:bad")
    assert not invalid["committed"] and invalid["partial_commit_count"] == 0 and canonical_digest(value) == before
    valid = ObjectTransaction(value).commit({"state_updates": {"ruo:state:committed": {"status": "done"}}}, source_revision="ruo:revision:0", transaction_id="ruo:transaction:good")
    assert valid["committed"] and value["current_revision"] == "ruo:revision:1"
    snapshot = copy.deepcopy(value); projection = generate_execution_projection(value)
    assert value == snapshot and projection_is_current(value, projection)
    value["current_revision"] = "ruo:revision:2"
    assert not projection_is_current(value, projection)

def test_queries_preserve_partial_knowledge_and_stable_ordering() -> None:
    value = reference_object()
    value["partial_loading"] = {"is_partial": True, "entity_status": {"ruo:unit:remote": "not_loaded"}, "unattached_retained_entities": []}
    assert query_object(value, "owner", "ruo:payload:text") == "ruo:unit:text"
    assert query_object(value, "knowledge_status", "ruo:unit:remote") == "not_loaded"
    assert query_object(value, "knowledge_status", "ruo:unit:absent") == "absent"
    assert query_object(value, "execution_eligible_units") == sorted(query_object(value, "execution_eligible_units"))

def test_offline_validation_determinism_resource_limit_and_tamper(generated: Path) -> None:
    assert validate_universal_model(ROOT, generated, verify_determinism=True)["ok"]
    assert "RUO-U1-027" in {item["code"] for item in validate_object(reference_object(), limits={"object_bytes": 1})}
    target = generated / "state_model_contract.json"; target.write_bytes(target.read_bytes() + b"\n")
    result = validate_universal_model(ROOT, generated, verify_determinism=False)
    assert not result["ok"] and "RUO-U1-025" in {item["code"] for item in result["issues"]}
