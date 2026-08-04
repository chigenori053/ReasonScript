from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from toolchain.reasonunit_compatibility import (
    CANONICAL_ARTIFACTS,
    PROFILE,
    ObjectTransaction,
    compare_semantics,
    derived_state_is_stale,
    generate_compatibility,
    invalidate_evidence,
    project_existing_runtime_view,
    query_compatibility,
    unwrap_legacy_units,
    validate_compatibility,
    validate_wrapped_object,
    verify_ruo_c0,
    wrap_legacy_units,
)
from toolchain.reasonunit_compatibility.model import projection_is_current

ROOT = Path(__file__).resolve().parents[2]
C0 = ROOT / "artifacts/reasonunit_baseline/ruo_c0"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def legacy() -> list[dict]:
    return [
        {"unit_id": "unit:a", "kind": "atomic_reasonunit", "state": {"value": 1}, "revision": 2, "lifecycle": "active", "dependencies": []},
        {"unit_id": "unit:b", "kind": "atomic_reasonunit", "state": {"value": 2}, "revision": 1, "lifecycle": "active", "dependencies": ["unit:a"], "local_custom": "preserve"},
        {"unit_id": "unit:c", "kind": "atomic_reasonunit", "state": {"value": 3}, "revision": 0, "lifecycle": "suspended"},
    ]


@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "ruo-c1"
    result = generate_compatibility(ROOT, output)
    assert result["phase_status"] == "VALIDATED"
    return output


def test_verified_ruo_c0_is_required_and_complete(tmp_path: Path) -> None:
    result = verify_ruo_c0(C0)
    assert result["ok"]
    assert result["summary"] == {"passed": 40, "failed": 0, "total": 40}
    copied = tmp_path / "c0"
    copied.mkdir()
    assert not verify_ruo_c0(copied)["ok"]
    result = generate_compatibility(ROOT, tmp_path / "output", c0_directory=copied)
    assert result["phase_status"] == "NOT_VALIDATED"
    assert result["artifact_count"] == 0


def test_generates_exactly_26_canonical_artifacts(generated: Path) -> None:
    assert {path.name for path in generated.iterdir()} == set(CANONICAL_ARTIFACTS)
    manifest = read(generated / "run_manifest.json")["data"]
    assert manifest["artifact_count"] == 26
    assert len(manifest["artifacts"]) == 26


def test_all_json_artifacts_use_project_schema(generated: Path) -> None:
    schema = read(ROOT / "schemas/reasonunit_compatibility/canonical_artifact.schema.json")
    assert schema["properties"]["profile_version"]["const"] == PROFILE
    for path in generated.glob("*.json"):
        value = read(path)
        assert value["profile_version"] == PROFILE
        assert value["schema_version"].startswith("reasonscript-reasonunit-compatibility-")
        assert set(value) == {"schema_version", "profile_version", "data"}


def test_matrix_is_t001_through_t056(generated: Path) -> None:
    summary = read(generated / "validation_summary.json")["data"]
    assert [item["test_id"] for item in summary["tests"]] == [f"RUO-C1-T{index:03}" for index in range(1, 57)]
    assert summary["summary"] == {"passed": 56, "failed": 0, "total": 56}
    assert summary["statuses"]["phase_status"] == "VALIDATED"
    assert summary["statuses"]["transition_decision"] == "PROCEED_TO_RUO-U1"


def test_wrap_validate_unwrap_is_lossless_and_namespaces_unknown_fields(legacy: list[dict]) -> None:
    wrapped = wrap_legacy_units(legacy, object_id="object:test")
    assert not validate_wrapped_object(wrapped)
    assert [unit["unit_id"] for unit in wrapped["unit_registry"]] == ["unit:a", "unit:b", "unit:c"]
    unit_b = next(unit for unit in wrapped["unit_registry"] if unit["unit_id"] == "unit:b")
    assert unit_b["extensions"]["legacy:unknown_fields"] == {"local_custom": "preserve"}
    result = compare_semantics(legacy, unwrap_legacy_units(wrapped))
    assert result["semantic_loss_count"] == 0
    assert all(value is True for key, value in result.items() if key != "semantic_loss_count")


def test_identity_ownership_containment_and_relation_diagnostics(legacy: list[dict]) -> None:
    duplicate = wrap_legacy_units([legacy[0], legacy[0]], object_id="object:test")
    assert "RUO-C1-003" in {item["code"] for item in validate_wrapped_object(duplicate)}
    multiple = wrap_legacy_units(legacy, object_id="object:test")
    multiple["ownership_graph"].append({"object_id": "object:other", "unit_id": "unit:a"})
    assert "RUO-C1-005" in {item["code"] for item in validate_wrapped_object(multiple)}
    cycle = wrap_legacy_units(legacy, object_id="object:test")
    cycle["unit_registry"][0]["parent_unit_id"] = "unit:b"
    cycle["unit_registry"][1]["parent_unit_id"] = "unit:a"
    assert "RUO-C1-006" in {item["code"] for item in validate_wrapped_object(cycle)}
    dangling = wrap_legacy_units(legacy, object_id="object:test")
    dangling["relation_registry"] = [{"relation_id": "relation:x", "source_id": "unit:a", "target_id": "unit:missing", "relation_type": "directed"}]
    assert "RUO-C1-008" in {item["code"] for item in validate_wrapped_object(dangling)}


def test_projection_closure_lifecycle_staleness_and_tensor_identity(legacy: list[dict]) -> None:
    wrapped = wrap_legacy_units(legacy, object_id="object:test")
    wrapped["tensor_index_table"] = [{"index": 0, "unit_id": "unit:b"}, {"index": 1, "unit_id": "unit:a"}]
    projection = project_existing_runtime_view(wrapped, ["unit:b"])
    assert projection["selected_unit_ids"] == ["unit:a", "unit:b"]
    assert projection["dependency_closure"] == ["unit:a", "unit:b"]
    assert projection_is_current(wrapped, projection)
    wrapped["revision"] += 1
    assert not projection_is_current(wrapped, projection)
    bad = copy.deepcopy(wrapped)
    bad["tensor_index_table"] = [{"index": "unit:a", "unit_id": "unit:a"}]
    assert "RUO-C1-015" in {item["code"] for item in validate_wrapped_object(bad)}


def test_evidence_deduplication_staleness_invalidation_and_queries(legacy: list[dict]) -> None:
    shared = {"evidence_id": "evidence:1", "source_reference": "fixture://source", "confidence": 0.8, "provenance": "observed"}
    legacy[0]["evidence"] = [shared]
    legacy[1]["evidence"] = [shared]
    wrapped = wrap_legacy_units(legacy, object_id="object:test")
    assert len(wrapped["evidence_registry"]) == 1
    assert wrapped["evidence_registry"][0]["supports"] == ["unit:a", "unit:b"]
    assert query_compatibility(wrapped, "owner_of_unit", "unit:a") == "object:test"
    assert [item["evidence_id"] for item in query_compatibility(wrapped, "supporting_evidence", "unit:a")] == ["evidence:1"]
    assert invalidate_evidence(wrapped, ["unit:a"], revision_id="revision:1") == ["evidence:1"]
    wrapped["state_registry"].append({"state_id": "state:derived", "owner_kind": "derived", "owner_id": "unit:b", "value": 3, "source_revisions": {"unit:a": 1}})
    assert derived_state_is_stale(wrapped, "state:derived")


def test_object_transaction_commits_or_rolls_back_atomically(legacy: list[dict]) -> None:
    wrapped = wrap_legacy_units(legacy, object_id="object:test")
    result = ObjectTransaction(wrapped).commit({"state:unit:a": {"value": 9}}, expected_revision=0, transaction_id="transaction:1")
    assert result["committed"] and result["partial_commit_count"] == 0
    assert wrapped["revision"] == 1
    assert next(unit for unit in wrapped["unit_registry"] if unit["unit_id"] == "unit:a")["revision"] == 3
    assert next(unit for unit in wrapped["unit_registry"] if unit["unit_id"] == "unit:b")["revision"] == 1
    before = copy.deepcopy(wrapped)
    result = ObjectTransaction(wrapped).commit({"state:missing": 4}, expected_revision=1, transaction_id="transaction:2")
    assert not result["committed"] and result["partial_commit_count"] == 0
    assert wrapped == before


def test_fixture_manifest_covers_required_valid_and_invalid_classes(generated: Path) -> None:
    fixtures = read(generated / "compatibility_fixture_manifest.json")["data"]
    assert len(fixtures["fixtures"]) == 9
    assert len(fixtures["invalid_fixtures"]) == 13
    vehicle = next(item for item in fixtures["fixtures"] if item["fixture_id"] == "vehicle")
    assert vehicle["class"] == "project_local_structured_object_precursor"
    assert vehicle["native_reasonunit_object"] is False


def test_offline_validation_determinism_and_tamper_detection(generated: Path, tmp_path: Path) -> None:
    assert validate_compatibility(ROOT, generated, verify_determinism=True)["ok"]
    target = generated / "state_ownership_contract.json"
    target.write_bytes(target.read_bytes() + b"\n")
    result = validate_compatibility(ROOT, generated, verify_determinism=False)
    assert not result["ok"]
    assert "RUO-C1-019" in {item["code"] for item in result["issues"]}
