from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from toolchain.reasonunit_file import (
    CANONICAL_ARTIFACTS,
    RUOFileError,
    generate_file_format,
    inspect_file,
    read_file,
    select_file,
    validate_file,
    validate_file_format,
    verify_resources,
    verify_ruo_u1,
    write_file,
)
from toolchain.reasonunit_file.format import canonical_json_bytes, encode_file
from toolchain.reasonunit_file.phase import FIXTURE_PATHS, PROFILE, _complete_object
from toolchain.reasonunit_file_cmd import run as cli_run
from toolchain.reasonunit_object.model import canonical_digest
from toolchain.reasonunit_object.universal import reference_object

ROOT = Path(__file__).resolve().parents[2]

def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "ruo-f1"
    assert generate_file_format(ROOT, output)["phase_status"] == "VALIDATED"
    return output

def test_u1_prerequisite_is_verified_and_required(tmp_path: Path) -> None:
    result = verify_ruo_u1(ROOT)
    assert result["ok"] and result["summary"] == {"passed": 65, "failed": 0, "total": 65}
    assert result["evidence"]["repository_tests"] == 1002
    missing = tmp_path / "missing"; missing.mkdir()
    assert generate_file_format(ROOT, tmp_path / "out", u1_directory=missing)["phase_status"] == "NOT_VALIDATED"

def test_canonical_write_read_validate_and_byte_roundtrip(tmp_path: Path) -> None:
    logical = reference_object(); target = tmp_path / "object.ruo"
    result = write_file(logical, target)
    assert result["ok"] and target.read_bytes().endswith(b"\n")
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf") and b"\r" not in target.read_bytes()
    decoded = read_file(target)
    assert canonical_digest(decoded) == canonical_digest(logical)
    assert encode_file(decoded) == target.read_bytes()
    assert validate_file(target)["semantic_status"] == "VALID"

def test_strict_physical_json_canonical_and_integrity_rejections(tmp_path: Path) -> None:
    canonical = encode_file(reference_object())
    cases = {
        "bom": b"\xef\xbb\xbf" + canonical,
        "crlf": canonical.replace(b"\n", b"\r\n", 1),
        "no-final-lf": canonical[:-1],
        "blank": canonical.replace(b"\n", b"\n\n", 1),
        "duplicate-key": canonical.replace(b'{"body":', b'{"body":{},"body":', 1),
        "whitespace": canonical.replace(b'{"body":', b'{ "body":', 1),
        "body-tamper": canonical.replace(b"universal", b"UniversaL", 1),
        "ordinal": canonical.replace(b'"ordinal":2', b'"ordinal":3', 1),
    }
    for name, payload in cases.items():
        path = tmp_path / f"{name}.ruo"; path.write_bytes(payload)
        assert not validate_file(path)["ok"], name

def test_record_sections_seal_and_logical_digest_are_verified(tmp_path: Path) -> None:
    path = tmp_path / "complete.ruo"; path.write_bytes(encode_file(_complete_object()))
    result = validate_file(path)
    assert result["ok"] and result["record_count"] > 20
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["record_type"] == "file_header" and records[1]["record_type"] == "section_manifest"
    assert records[-1]["record_type"] == "file_seal"
    assert records[-1]["body"]["content_record_count"] == len(records) - 1

def test_external_resource_digest_chunks_and_path_safety(tmp_path: Path) -> None:
    root = tmp_path / "bundle"; resources = root / "resources"; resources.mkdir(parents=True)
    payload = b"ReasonUnit external payload\n"; (resources / "payload.bin").write_bytes(payload)
    file = root / "object.ruo"; file.write_bytes(encode_file(_complete_object()))
    assert verify_resources(file, root)["ok"]
    (resources / "payload.bin").write_bytes(b"corrupt")
    assert not verify_resources(file, root)["ok"]
    unsafe = _complete_object(); unsafe["external_resources"][0]["locator"] = "../secret"
    bad = root / "unsafe.ruo"; bad.write_bytes(encode_file(unsafe))
    assert not validate_file(bad)["ok"]

def test_unknown_extension_modes_and_inspect_semantics(tmp_path: Path) -> None:
    value = reference_object(); value["extension_registry"].append({"authority": "future", "canonical_ordering": "key", "critical": False, "namespace": "future", "opaque_retention": True, "version": "1"})
    file = tmp_path / "preserve.ruo"; file.write_bytes(encode_file(value))
    decoded = read_file(file, mode="preserve")
    assert any(item["namespace"] == "future" for item in decoded["extension_registry"])
    inspected = inspect_file(file)
    assert inspected["ok"] and inspected["semantic_status"] == "NOT_EVALUATED"
    value["extension_registry"][-1]["critical"] = True
    critical = tmp_path / "critical.ruo"; critical.write_bytes(encode_file(value))
    assert not validate_file(critical)["ok"]

def test_partial_selection_preserves_not_loaded_and_statuses(tmp_path: Path) -> None:
    complete = tmp_path / "complete.ruo"; complete.write_bytes(encode_file(_complete_object()))
    partial = tmp_path / "partial.ruo"
    selector = {"containment_roots": ["ruo:unit:root"], "containment_depth": 1, "include_evidence_closure": True, "include_dependency_closure": True}
    assert select_file(complete, selector, partial)["ok"]
    result = validate_file(partial); logical = read_file(partial)
    assert result["semantic_status"] == "INDETERMINATE"
    assert logical["partial_loading"]["is_partial"] is True
    assert set(logical["partial_loading"]["entity_status"].values()) == {"not_loaded"}

def test_atomic_writer_requires_explicit_replacement_and_preserves_target(tmp_path: Path) -> None:
    target = tmp_path / "object.ruo"; write_file(reference_object(), target); before = target.read_bytes()
    with pytest.raises(RUOFileError): write_file(reference_object(), target)
    assert target.read_bytes() == before
    with pytest.raises(RUOFileError): write_file(reference_object(), target, expected_digest="incorrect")
    assert target.read_bytes() == before
    assert write_file(reference_object(), target, overwrite=True)["ok"]

def test_limits_and_invalid_logical_object_prevent_publication(tmp_path: Path) -> None:
    source = tmp_path / "source.ruo"; source.write_bytes(encode_file(reference_object()))
    assert not validate_file(source, limits={"file_bytes": 1})["ok"]
    invalid = reference_object(); invalid["units"][0]["owner_object_id"] = "ruo:object:other"
    target = tmp_path / "invalid.ruo"
    with pytest.raises(RUOFileError): write_file(invalid, target)
    assert not target.exists()

def test_cli_operations_return_stable_json_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    logical_path = tmp_path / "input.json"; logical_path.write_text(json.dumps(reference_object(), ensure_ascii=False), encoding="utf-8")
    file = tmp_path / "object.ruo"
    assert cli_run(["write", str(logical_path), "--output", str(file), "--json"], ROOT) == 0
    write_result = json.loads(capsys.readouterr().out); assert write_result["command"] == "write" and write_result["exit_status"] == 0
    assert cli_run(["validate", str(file), "--json"], ROOT) == 0
    validate_result = json.loads(capsys.readouterr().out); assert validate_result["semantic_status"] == "VALID"
    assert cli_run(["inspect", str(file), "--json"], ROOT) == 0
    inspect_result = json.loads(capsys.readouterr().out); assert inspect_result["semantic_status"] == "NOT_EVALUATED"
    output = tmp_path / "output.json"; assert cli_run(["read", str(file), "--output", str(output), "--json"], ROOT) == 0
    assert json.loads(capsys.readouterr().out)["ok"] and output.is_file()

def test_phase_generates_38_artifacts_and_three_fixtures(generated: Path) -> None:
    assert all((generated / name).is_file() for name in [*CANONICAL_ARTIFACTS, *FIXTURE_PATHS])
    manifest = read_json(generated / "run_manifest.json")["data"]
    assert manifest["artifact_count"] == 38 and manifest["fixture_count"] == 3 and len(manifest["files"]) == 41
    for path in generated.glob("*.json"):
        value = read_json(path); assert value["profile_version"] == PROFILE and set(value) == {"schema_version", "profile_version", "data"}

def test_matrix_offline_validation_determinism_and_tamper(generated: Path) -> None:
    summary = read_json(generated / "validation_summary.json")["data"]
    assert [item["test_id"] for item in summary["tests"]] == [f"RUO-F1-T{i:03}" for i in range(1, 73)]
    assert summary["summary"] == {"passed": 72, "failed": 0, "total": 72}
    assert summary["statuses"]["transition_decision"] == "PROCEED_TO_RUO-T1"
    assert validate_file_format(ROOT, generated, verify_determinism=True)["ok"]
    target = generated / "reader_contract.json"; target.write_bytes(target.read_bytes() + b"\n")
    result = validate_file_format(ROOT, generated, verify_determinism=False)
    assert not result["ok"] and "RUO-F1-027" in {item["code"] for item in result["issues"]}
