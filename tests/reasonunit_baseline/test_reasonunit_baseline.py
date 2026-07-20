from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from toolchain.reasonunit_baseline.baseline import (
    CANONICAL_ARTIFACTS,
    PROFILE,
    SEMANTIC_OWNERS,
    generate_baseline,
    sha256_bytes,
    validate_baseline,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "ruo-c0"
    generate_baseline(ROOT, output)
    return output


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def descriptor(path: Path, manifest_dir: Path) -> dict[str, str]:
    return {"local_path": path.relative_to(manifest_dir).as_posix(), "sha256": sha256_bytes(path.read_bytes())}


def valid_g1_summary() -> dict[str, Any]:
    return {
        "schema_version": "ruo-g1-validation-summary/1.0",
        "phase_status": "VALIDATED",
        "test_totals": {"passed": 26, "failed": 0, "total": 26},
        "test_matrix": {f"RUO-G1-T{index:03}": True for index in range(1, 27)},
        "pytest": {"passed": True, "returncode": 0},
        "determinism": {"runs": 3, "byte_identical": True, "offline_validation_problems": []},
        "revision_procedure": {
            "invalid_revision": {"committed": False, "partial_commit_count": 0},
        },
    }


def valid_g1e_summary() -> dict[str, Any]:
    return {
        "schema_version": "ruo-g1e/1.0",
        "artifact_type": "validation_summary",
        "phase_status": "VALIDATED",
        "passed": 36,
        "failed": 0,
        "test_count": 36,
        "results": [{"test_id": f"RUO-G1E-T{index:03}", "status": "PASS"} for index in range(1, 37)],
        "ruo_g1_regression": "26/26 PASS",
    }


def valid_density() -> dict[str, Any]:
    return {
        "schema_version": "ruo-g1e/1.0",
        "artifact_type": "information_density_report",
        "semantic_component_count": 30,
        "curve_count": 72,
        "landmark_count": 48,
        "contour_count": 12,
        "relation_count": 150,
        "evidence_coverage": 1.0,
        "useful_information_increased": True,
        "reason_unit_count": 31,
        "dependency_edge_count": 120,
    }


def make_external_bundles(tmp_path: Path) -> dict[str, Any]:
    manifest_dir = tmp_path / "external"
    g1_root = manifest_dir / "g1"
    g1_dir = g1_root / "canonical"
    g1e_root = manifest_dir / "g1e"
    g1e_dir = g1e_root / "canonical"
    g1_summary = g1_root / "validation_summary.json"
    write_json(g1_summary, valid_g1_summary())
    g1_children = []
    for index in range(1, 11):
        child = g1_dir / f"canonical_{index:02}.json"
        write_json(child, {"artifact": index})
        g1_children.append(child)
    g1_run = g1_dir / "run_manifest.json"
    write_json(g1_run, {
        "schema_version": "ruo-g1-run-manifest/1.0",
        "artifact_digests": {child.name: sha256_bytes(child.read_bytes()) for child in g1_children},
        "geometry_digest": "a" * 64,
    })

    g1e_summary = g1e_root / "validation_summary.json"
    density = g1e_dir / "information_density_report.json"
    write_json(g1e_summary, valid_g1e_summary())
    write_json(density, valid_density())
    required = [
        density,
        g1e_dir / "projection_l0.json",
        g1e_dir / "projection_l1.json",
        g1e_dir / "projection_l2.json",
    ]
    for child in required[1:]:
        write_json(child, {"projection": child.stem})
    g1e_children = list(required)
    for index in range(1, 18):
        child = g1e_dir / f"canonical_{index:02}.json"
        write_json(child, {"artifact": index})
        g1e_children.append(child)
    assert len(g1e_children) == 21
    g1e_run = g1e_dir / "run_manifest.json"
    entries = [{"path": child.name, "sha256": sha256_bytes(child.read_bytes()), "byte_size": child.stat().st_size} for child in g1e_children]
    write_json(g1e_run, {
        "schema_version": "ruo-g1e/1.0",
        "artifact_type": "run_manifest",
        "self_digest_excluded": True,
        "artifacts": entries,
        "total_bytes": sum(entry["byte_size"] for entry in entries),
    })

    manifest = manifest_dir / "evidence.json"
    manifest_value = {
        "evidence": [
            {
                "project_id": "vehicle-silhouette-ruo-g1",
                "artifact_id": "RUO-G1",
                "files": {
                    "validation_summary": descriptor(g1_summary, manifest_dir),
                    "run_manifest": descriptor(g1_run, manifest_dir),
                },
            },
            {
                "project_id": "vehicle-silhouette-ruo-g1",
                "artifact_id": "RUO-G1E",
                "files": {
                    "validation_summary": descriptor(g1e_summary, manifest_dir),
                    "run_manifest": descriptor(g1e_run, manifest_dir),
                    "information_density_report": descriptor(density, manifest_dir),
                },
            },
        ]
    }
    write_json(manifest, manifest_value)
    return {
        "manifest": manifest,
        "manifest_value": manifest_value,
        "manifest_dir": manifest_dir,
        "g1_summary": g1_summary,
        "g1_run": g1_run,
        "g1_dir": g1_dir,
        "g1e_summary": g1e_summary,
        "g1e_run": g1e_run,
        "density": density,
        "g1e_dir": g1e_dir,
    }


def refresh_descriptor(bundle: dict[str, Any], artifact_id: str, role: str, path: Path) -> None:
    item = next(item for item in bundle["manifest_value"]["evidence"] if item["artifact_id"] == artifact_id)
    item["files"][role] = descriptor(path, bundle["manifest_dir"])
    write_json(bundle["manifest"], bundle["manifest_value"])


def external_reasons(output: Path) -> set[str]:
    diagnostics = read(output / "diagnostics.json")["data"]["diagnostics"]
    return {item["metadata"]["reason"] for item in diagnostics}


def generate_with_bundle(tmp_path: Path, bundle: dict[str, Any]) -> Path:
    output = tmp_path / "ruo-c0"
    generate_baseline(ROOT, output, external_manifest=bundle["manifest"])
    return output


def test_generates_complete_canonical_artifact_set(generated: Path) -> None:
    assert {path.name for path in generated.iterdir()} == set(CANONICAL_ARTIFACTS)
    manifest = read(generated / "run_manifest.json")
    assert manifest["data"]["artifact_count"] == 20
    assert len(manifest["data"]["artifacts"]) == 20


def test_all_json_artifacts_use_versioned_project_schema(generated: Path) -> None:
    for path in sorted(generated.glob("*.json")):
        document = read(path)
        assert document["profile_version"] == PROFILE
        assert document["schema_version"].startswith("reasonscript-reasonunit-baseline-")
        assert document["schema_version"].endswith("/1.0")


def test_contract_inventory_classifies_every_field(generated: Path) -> None:
    inventory = read(generated / "reasonunit_contract_inventory.json")["data"]
    assert len(inventory["fields"]) == 14
    assert all(item["semantic_owner"] in SEMANTIC_OWNERS for item in inventory["fields"])


def test_fixture_manifest_covers_required_valid_and_invalid_classes(generated: Path) -> None:
    fixtures = read(generated / "golden_fixture_manifest.json")["data"]
    assert {item["class"] for item in fixtures["fixtures"]} == {
        "minimal_atomic", "related", "stateful", "evidence_carrying",
        "lifecycle", "cluster_executed", "tensor_associated", "molecular_structured",
    }
    assert len(fixtures["invalid_fixtures"]) == 8


def test_test_matrix_has_stable_t001_t040_ids(generated: Path) -> None:
    tests = read(generated / "validation_summary.json")["data"]["tests"]
    assert [item["test_id"] for item in tests] == [f"RUO-C0-T{index:03}" for index in range(1, 41)]


def test_missing_external_vehicle_evidence_prevents_transition(generated: Path) -> None:
    summary = read(generated / "validation_summary.json")["data"]
    assert summary["statuses"]["phase_status"] == "NOT_VALIDATED"
    assert summary["statuses"]["transition_decision"] == "DO_NOT_PROCEED_TO_RUO-C1"
    assert {item["test_id"] for item in summary["tests"] if item["status"] == "fail"} == {"RUO-C0-T028", "RUO-C0-T029"}


def test_three_generations_are_byte_identical(tmp_path: Path) -> None:
    runs = [tmp_path / f"run-{index}" for index in range(3)]
    for run in runs:
        generate_baseline(ROOT, run)
    for name in CANONICAL_ARTIFACTS:
        assert (runs[0] / name).read_bytes() == (runs[1] / name).read_bytes() == (runs[2] / name).read_bytes()


def test_manifest_detects_copied_artifact_tampering(generated: Path) -> None:
    manifest = read(generated / "run_manifest.json")["data"]
    entry = next(item for item in manifest["artifacts"] if item["path"] == "reasonunit_state_baseline.json")
    assert sha256_bytes((generated / entry["path"]).read_bytes() + b"tamper") != entry["sha256"]


def test_offline_validator_reports_only_external_mandatory_failures(generated: Path) -> None:
    result = validate_baseline(ROOT, generated, verify_determinism=True)
    assert not result["ok"]
    assert result["issues"] == []
    assert {item["test_id"] for item in result["mandatory_failures"]} == {"RUO-C0-T028", "RUO-C0-T029"}
    assert result["tests"] == {"T037": "pass", "T038": "pass", "T039": "pass"}


def test_valid_self_contained_external_bundles_validate(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    output = generate_with_bundle(tmp_path, bundle)
    summary = read(output / "validation_summary.json")["data"]
    assert summary["summary"] == {"passed": 40, "failed": 0, "total": 40}
    assert summary["statuses"]["phase_status"] == "VALIDATED"
    assert summary["statuses"]["transition_decision"] == "PROCEED_TO_RUO-C1"
    evidence = read(output / "project_evidence_manifest.json")["data"]["evidence"]
    vehicle = [item for item in evidence if item["artifact_id"] in {"RUO-G1", "RUO-G1E"}]
    assert all(item["verified"] for item in vehicle)
    assert all(set(item) == {"project_id", "artifact_id", "schema_or_profile", "content_digests", "verified", "claims"} for item in vehicle)
    assert str(bundle["manifest_dir"]) not in (output / "project_evidence_manifest.json").read_text(encoding="utf-8")
    assert read(output / "diagnostics.json")["data"]["diagnostics"] == []
    assert validate_baseline(ROOT, output, external_manifest=bundle["manifest"])["ok"]


def test_validation_summaries_are_independent_of_canonical_manifests(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    assert bundle["g1_summary"].parent != bundle["g1_run"].parent
    assert bundle["g1e_summary"].parent != bundle["g1e_run"].parent
    assert "validation_summary.json" not in read(bundle["g1_run"])["artifact_digests"]
    assert "validation_summary.json" not in {entry["path"] for entry in read(bundle["g1e_run"])["artifacts"]}
    output = generate_with_bundle(tmp_path, bundle)
    assert read(output / "validation_summary.json")["data"]["statuses"]["phase_status"] == "VALIDATED"


def test_g1_nested_invalid_revision_contract_is_accepted(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    summary = read(bundle["g1_summary"])
    assert summary["revision_procedure"]["invalid_revision"] == {"committed": False, "partial_commit_count": 0}
    output = generate_with_bundle(tmp_path, bundle)
    assert read(output / "validation_summary.json")["data"]["tests"][27]["status"] == "pass"


def test_arbitrary_json_with_matching_self_supplied_digest_is_rejected(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    write_json(bundle["g1_summary"], {"hello": "unrelated"})
    refresh_descriptor(bundle, "RUO-G1", "validation_summary", bundle["g1_summary"])
    output = generate_with_bundle(tmp_path, bundle)
    assert {"unrelated_json", "wrong_schema", "phase_not_validated", "count_mismatch", "missing_or_failed_test"}.issubset(external_reasons(output))
    assert read(output / "validation_summary.json")["data"]["tests"][27]["status"] == "fail"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda value: value.update(phase_status="NOT_VALIDATED"), "phase_not_validated"),
        (lambda value: value.update(test_totals={"passed": 25, "failed": 1, "total": 26}), "count_mismatch"),
        (lambda value: value["test_matrix"].pop("RUO-G1-T026"), "missing_or_failed_test"),
        (lambda value: value["test_matrix"].update({"RUO-G1-T026": False}), "missing_or_failed_test"),
        (lambda value: value.update(schema_version="ruo-g1-validation-summary/9.9"), "wrong_schema"),
    ],
    ids=["phase-not-validated", "25-of-26", "missing-test-id", "failed-test", "wrong-schema"],
)
def test_invalid_g1_summary_is_rejected(tmp_path: Path, mutation: Callable[[dict[str, Any]], None], reason: str) -> None:
    bundle = make_external_bundles(tmp_path)
    value = read(bundle["g1_summary"])
    mutation(value)
    write_json(bundle["g1_summary"], value)
    refresh_descriptor(bundle, "RUO-G1", "validation_summary", bundle["g1_summary"])
    assert reason in external_reasons(generate_with_bundle(tmp_path, bundle))


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda value: value.update(passed=35, failed=1), "count_mismatch"),
        (lambda value: value["results"].pop(), "missing_or_failed_test"),
        (lambda value: value["results"][0].update(status="FAIL"), "missing_or_failed_test"),
        (lambda value: value.update(schema_version="ruo-g1e/9.9"), "wrong_schema"),
    ],
    ids=["35-of-36", "missing-test-id", "failed-test", "wrong-schema"],
)
def test_invalid_g1e_summary_is_rejected(tmp_path: Path, mutation: Callable[[dict[str, Any]], None], reason: str) -> None:
    bundle = make_external_bundles(tmp_path)
    value = read(bundle["g1e_summary"])
    mutation(value)
    write_json(bundle["g1e_summary"], value)
    refresh_descriptor(bundle, "RUO-G1E", "validation_summary", bundle["g1e_summary"])
    assert reason in external_reasons(generate_with_bundle(tmp_path, bundle))


def test_component_count_29_is_rejected(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    value = read(bundle["density"])
    value["semantic_component_count"] = 29
    write_json(bundle["density"], value)
    refresh_descriptor(bundle, "RUO-G1E", "information_density_report", bundle["density"])
    assert "count_mismatch" in external_reasons(generate_with_bundle(tmp_path, bundle))


def rewrite_g1e_run(bundle: dict[str, Any], value: dict[str, Any]) -> None:
    write_json(bundle["g1e_run"], value)
    refresh_descriptor(bundle, "RUO-G1E", "run_manifest", bundle["g1e_run"])


@pytest.mark.parametrize("projection", ["projection_l0.json", "projection_l1.json", "projection_l2.json"])
def test_missing_projection_is_rejected(tmp_path: Path, projection: str) -> None:
    bundle = make_external_bundles(tmp_path)
    value = read(bundle["g1e_run"])
    value["artifacts"] = [entry for entry in value["artifacts"] if entry["path"] != projection]
    value["total_bytes"] = sum(entry["byte_size"] for entry in value["artifacts"])
    rewrite_g1e_run(bundle, value)
    assert "child_artifact_missing" in external_reasons(generate_with_bundle(tmp_path, bundle))


def test_missing_g1e_information_density_child_is_rejected(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    value = read(bundle["g1e_run"])
    value["artifacts"] = [entry for entry in value["artifacts"] if entry["path"] != "information_density_report.json"]
    value["total_bytes"] = sum(entry["byte_size"] for entry in value["artifacts"])
    rewrite_g1e_run(bundle, value)
    reasons = external_reasons(generate_with_bundle(tmp_path, bundle))
    assert "child_artifact_missing" in reasons
    assert "child_digest_mismatch" in reasons


def test_modified_child_artifact_is_rejected(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    child = bundle["g1e_dir"] / "projection_l1.json"
    child.write_bytes(child.read_bytes() + b"tampered")
    assert "child_digest_mismatch" in external_reasons(generate_with_bundle(tmp_path, bundle))


def test_incorrect_child_byte_size_is_rejected(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    value = read(bundle["g1e_run"])
    value["artifacts"][0]["byte_size"] += 1
    value["total_bytes"] += 1
    rewrite_g1e_run(bundle, value)
    assert "child_size_mismatch" in external_reasons(generate_with_bundle(tmp_path, bundle))


def test_external_descriptor_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    item = next(item for item in bundle["manifest_value"]["evidence"] if item["artifact_id"] == "RUO-G1E")
    item["files"]["validation_summary"]["sha256"] = "sha256:" + "0" * 64
    write_json(bundle["manifest"], bundle["manifest_value"])
    assert "digest_mismatch" in external_reasons(generate_with_bundle(tmp_path, bundle))


def test_malformed_external_json_has_deterministic_diagnostic(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    bundle["g1_summary"].write_bytes(b"{not-json")
    refresh_descriptor(bundle, "RUO-G1", "validation_summary", bundle["g1_summary"])
    assert "malformed_json" in external_reasons(generate_with_bundle(tmp_path, bundle))


def test_wrong_external_artifact_role_has_deterministic_diagnostic(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    value = read(bundle["g1e_summary"])
    value["artifact_type"] = "information_density_report"
    write_json(bundle["g1e_summary"], value)
    refresh_descriptor(bundle, "RUO-G1E", "validation_summary", bundle["g1e_summary"])
    assert "wrong_artifact_role" in external_reasons(generate_with_bundle(tmp_path, bundle))


def test_missing_external_file_has_deterministic_diagnostic(tmp_path: Path) -> None:
    bundle = make_external_bundles(tmp_path)
    item = next(item for item in bundle["manifest_value"]["evidence"] if item["artifact_id"] == "RUO-G1")
    item["files"]["validation_summary"]["local_path"] = "g1/missing.json"
    write_json(bundle["manifest"], bundle["manifest_value"])
    assert "missing_file" in external_reasons(generate_with_bundle(tmp_path, bundle))


@pytest.mark.parametrize("index", range(1, 41), ids=lambda value: f"RUO-C0-T{value:03}")
def test_matrix_requirement_is_present(generated: Path, index: int) -> None:
    tests = read(generated / "validation_summary.json")["data"]["tests"]
    entry = tests[index - 1]
    assert entry["test_id"] == f"RUO-C0-T{index:03}"
    assert entry["requirement"]
