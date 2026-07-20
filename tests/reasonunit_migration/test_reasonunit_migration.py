from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolchain.object_cmd import run as object_cli
from toolchain.reasonunit_file import read_file
from toolchain.reasonunit_migration import MigrationError, analyze, compare, convert, discover, dry_run, generate_migration_profile, plan, publish, rollback, status, validate, validate_migration_profile
from toolchain.reasonunit_migration.phase import CANONICAL_ARTIFACTS, DIAGNOSTIC_CODES, FIXTURE_CLASSES, verify_ruo_n2

ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


@pytest.fixture()
def workflow(tmp_path: Path) -> dict[str, Path]:
    source = tmp_path / "legacy.json"
    write_json(source, {"project_id": "p", "units": [{"id": "ruo:unit:root", "locator": "root", "kind": "composite", "children": ["leaf"]}, {"locator": "leaf", "payload": {"text": "hello"}}], "relations": [{"from": "root", "to": "leaf"}], "extension": {"x:y": 1}})
    inventory = tmp_path / "inventory.json"; analysis_path = tmp_path / "analysis.json"; plan_path = tmp_path / "plan.json"; staging = tmp_path / "staging"
    discover(source, inventory); write_json(analysis_path, analyze(inventory, "legacy-json/1")); plan(analysis_path, plan_path)
    return {"source": source, "inventory": inventory, "analysis": analysis_path, "plan": plan_path, "staging": staging}


def test_discovery_is_read_only_classified_and_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"; source.mkdir(); write_json(source / "b.json", {"x": 1}); write_json(source / "a.json", {"units": []})
    before = {p.name: p.read_bytes() for p in source.iterdir()}; first = discover(source, tmp_path / "one.json"); second = discover(source, tmp_path / "two.json")
    assert first == second and [e["relative_path"] for e in first["entries"]] == ["a.json", "b.json"]
    assert [e["classification"] for e in first["entries"]] == ["project_local", "documentation_only"] and before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_discovery_rejects_missing_invalid_and_symlink(tmp_path: Path) -> None:
    with pytest.raises(MigrationError, match="RUO-M1-002"): discover(tmp_path / "missing", tmp_path / "out")
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    with pytest.raises(MigrationError, match="RUO-M1-004"): discover(tmp_path / "bad.json", tmp_path / "out")
    target = tmp_path / "target.json"; write_json(target, {"units": []}); link = tmp_path / "link.json"; link.symlink_to(target)
    with pytest.raises(MigrationError, match="RUO-M1-021"): discover(link, tmp_path / "out")
    source_dir = tmp_path / "sources"; source_dir.mkdir(); write_json(source_dir / "x.json", {"units": []})
    with pytest.raises(MigrationError, match="RUO-M1-021"): discover(source_dir, source_dir / "inventory.json")


def test_analyze_rejects_inventory_without_supported_source(tmp_path: Path) -> None:
    source = tmp_path / "x.json"; write_json(source, {"other": []}); inventory = tmp_path / "i.json"; discover(source, inventory)
    with pytest.raises(MigrationError, match="RUO-M1-003"): analyze(inventory, "legacy-json/1")


def test_plan_preserves_explicit_and_generates_stable_semantic_ids(workflow: dict[str, Path]) -> None:
    value = json.loads(workflow["plan"].read_text()); mappings = value["migration_units"][0]["identity_mappings"]
    assert mappings[0]["target_id"] == "ruo:unit:root" and mappings[1]["target_id"].startswith("ruo:unit:")
    other = workflow["plan"].with_name("other.json"); plan(workflow["analysis"], other)
    assert json.loads(other.read_text()) == value


def test_plan_rejects_source_changed_after_freeze(workflow: dict[str, Path]) -> None:
    write_json(workflow["source"], {"project_id": "changed", "units": []})
    with pytest.raises(MigrationError, match="RUO-M1-015"): dry_run(workflow["plan"], workflow["staging"])


def test_plan_rejects_unsafe_project_name_and_identity_collision(tmp_path: Path) -> None:
    source = tmp_path / "legacy.json"; inventory, analysis_path = tmp_path / "i.json", tmp_path / "a.json"
    write_json(source, {"project_id": "../escape", "units": []}); discover(source, inventory); write_json(analysis_path, analyze(inventory, "legacy-json/1"))
    with pytest.raises(MigrationError, match="RUO-M1-004"): plan(analysis_path, tmp_path / "p.json")
    write_json(source, {"project_id": "safe", "units": [{"id": "ruo:unit:same", "locator": "a"}, {"id": "ruo:unit:same", "locator": "b"}]}); discover(source, inventory); write_json(analysis_path, analyze(inventory, "legacy-json/1"))
    with pytest.raises(MigrationError, match="RUO-M1-005"): plan(analysis_path, tmp_path / "p.json")


def test_plan_digest_tampering_is_rejected(workflow: dict[str, Path]) -> None:
    value = json.loads(workflow["plan"].read_text()); value["mapping_profile"] = "tampered"; write_json(workflow["plan"], value)
    with pytest.raises(MigrationError, match="RUO-M1-015"): convert(workflow["plan"], workflow["staging"])


def test_dry_run_only_writes_report_in_staging(workflow: dict[str, Path]) -> None:
    result = dry_run(workflow["plan"], workflow["staging"])
    assert result["writes_outside_staging"] == 0 and result["validation"] == "VALIDATED"
    assert (workflow["staging"] / "dry_run_report.json").is_file() and (workflow["staging"] / "objects/p.ruo").is_file()


def test_conversion_is_valid_and_retains_complete_legacy_source(workflow: dict[str, Path]) -> None:
    result = convert(workflow["plan"], workflow["staging"]); target = Path(result["records"][0]["path"]); converted = read_file(target)
    assert converted["object_identity"]["entity_id"].startswith("ruo:object:") and converted["extensions"]["legacy"]["relations"]
    assert converted["units"][0]["extensions"]["legacy"] and result["partial_commit_count"] == 0


def test_compare_validate_and_status_are_zero_loss(workflow: dict[str, Path]) -> None:
    convert(workflow["plan"], workflow["staging"])
    assert compare(workflow["plan"], workflow["staging"])["semantic_loss_count"] == 0
    assert validate(workflow["plan"], workflow["staging"])["status"] == "VALIDATED"
    assert status(workflow["plan"], workflow["staging"])["status"] == "VALIDATED"


def test_compare_detects_loss(workflow: dict[str, Path]) -> None:
    result = convert(workflow["plan"], workflow["staging"]); path = Path(result["records"][0]["path"]); value = read_file(path); value["extensions"]["legacy"].pop("relations")
    from toolchain.reasonunit_file import write_file
    write_file(value, path, overwrite=True)
    with pytest.raises(MigrationError, match="RUO-M1-016"): compare(workflow["plan"], workflow["staging"])


def test_publish_requires_capability_and_is_atomic(workflow: dict[str, Path]) -> None:
    convert(workflow["plan"], workflow["staging"]); target = workflow["plan"].parent / "active"
    with pytest.raises(MigrationError, match="RUO-M1-021"): publish(workflow["plan"], workflow["staging"], target, allow_write=False)
    result = publish(workflow["plan"], workflow["staging"], target, allow_write=True)
    assert result["status"] == "PUBLISHED" and (target / "active_migration.json").is_file() and (target / "consumer_binding.rsn").is_file() and result["partial_commit_count"] == 0
    assert publish(workflow["plan"], workflow["staging"], target, allow_write=True)["status"] == "ALREADY_PUBLISHED"


def test_publish_replaces_and_rollback_restores_previous_target(workflow: dict[str, Path]) -> None:
    convert(workflow["plan"], workflow["staging"]); target = workflow["plan"].parent / "active"; target.mkdir(); (target / "legacy.txt").write_text("old")
    published = publish(workflow["plan"], workflow["staging"], target, allow_write=True); rollback_file = Path(published["rollback"])
    with pytest.raises(MigrationError, match="RUO-M1-021"): rollback(rollback_file, allow_write=False)
    result = rollback(rollback_file, allow_write=True)
    assert result["status"] == "ROLLED_BACK" and (target / "legacy.txt").read_text() == "old" and Path(result["published_evidence"]).exists()


def test_conversion_is_idempotent(workflow: dict[str, Path], tmp_path: Path) -> None:
    first = convert(workflow["plan"], workflow["staging"]); second_staging = tmp_path / "other"; second = convert(workflow["plan"], second_staging)
    assert first["records"][0]["logical_digest"] == second["records"][0]["logical_digest"]
    assert (workflow["staging"] / "objects/p.ruo").read_bytes() == (second_staging / "objects/p.ruo").read_bytes()


def test_supported_tensor_migrates_to_t1_resource(tmp_path: Path) -> None:
    source = tmp_path / "legacy.json"; write_json(source, {"project_id": "tensor", "units": [{"locator": "root"}], "tensor": {"dtype": "int32", "shape": [2], "values": [3, 4]}})
    inventory, analysis_path, plan_path, staging = tmp_path / "i.json", tmp_path / "a.json", tmp_path / "p.json", tmp_path / "st"
    discover(source, inventory); write_json(analysis_path, analyze(inventory, "legacy-json/1")); plan(analysis_path, plan_path); convert(plan_path, staging)
    logical = read_file(staging / "objects/tensor.ruo")
    assert logical["payloads"][0]["profile_id"] == "ruo.payload.tensor/1" and (staging / "objects/resources/tensor.ruot").read_bytes()
    result = validate(plan_path, staging); assert result["results"][0] == {"project_id": "tensor", "ok": True, "u1_f1": True, "t1": True, "n1": True, "n2": True}


def test_cli_runs_full_staged_workflow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "legacy.json"; write_json(source, {"project_id": "cli", "units": [{"locator": "root"}]}); inventory = tmp_path / "i.json"; analysis_path = tmp_path / "a.json"; plan_path = tmp_path / "p.json"; staging = tmp_path / "st"
    assert object_cli(["migrate", "discover", str(source), "--output", str(inventory), "--json"], ROOT) == 0
    assert object_cli(["migrate", "analyze", str(inventory), "--profile", "legacy-json/1", "--output", str(analysis_path), "--json"], ROOT) == 0
    assert object_cli(["migrate", "plan", str(analysis_path), "--output", str(plan_path), "--json"], ROOT) == 0
    for operation in ("dry-run", "convert", "compare", "validate", "status"):
        assert object_cli(["migrate", operation, str(plan_path), "--staging", str(staging), "--json"], ROOT) == 0
    assert '"ok":true' in capsys.readouterr().out


def test_cli_reports_structured_capability_failure(workflow: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    convert(workflow["plan"], workflow["staging"])
    assert object_cli(["migrate", "publish", str(workflow["plan"]), "--staging", str(workflow["staging"]), "--target", str(workflow["plan"].parent / "x"), "--json"], ROOT) == 1
    output = json.loads(capsys.readouterr().out); assert output["diagnostics"][0]["code"] == "RUO-M1-021"


def test_n2_prerequisite_fixture_and_diagnostic_inventories() -> None:
    verified = verify_ruo_n2(ROOT); assert verified["ok"] and verified["summary"] == {"passed": 67, "failed": 0, "total": 67}
    assert len(FIXTURE_CLASSES) == 21 and len(DIAGNOSTIC_CODES) == 24


def test_phase_generation_validation_and_three_run_determinism(tmp_path: Path) -> None:
    output = tmp_path / "ruo-m1"; result = generate_migration_profile(ROOT, output)
    assert result == {"output": str(output.resolve()), "phase_status": "VALIDATED", "artifact_count": 57, "file_count": 63}
    assert len(CANONICAL_ARTIFACTS) == 57 and validate_migration_profile(ROOT, output)["ok"]
    summary = json.loads((output / "validation_summary.json").read_text())["data"]
    assert summary["summary"] == {"passed": 63, "failed": 0, "total": 63} and summary["statuses"]["transition_decision"] == "PROCEED_TO_RUO-W1"


def test_phase_rejects_missing_n2_prerequisite(tmp_path: Path) -> None:
    missing = tmp_path / "missing"; missing.mkdir()
    assert generate_migration_profile(ROOT, tmp_path / "out", n2_directory=missing)["phase_status"] == "NOT_VALIDATED"
