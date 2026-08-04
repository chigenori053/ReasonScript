from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from toolchain.reasonunit_file import write_file
from toolchain.reasonunit_object.universal import reference_object
from toolchain.reasonunit_runtime import CANONICAL_ARTIFACTS, generate_runtime_profile, validate_runtime_profile, verify_ruo_t1
from toolchain.reasonunit_runtime.phase import INVALID_CASES, NATIVE_TYPES, PROFILE
from toolchain.reasonunit_runtime_cmd import run as cli_run

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "ruo-n1"
    assert generate_runtime_profile(ROOT, output)["phase_status"] == "VALIDATED"
    return output


def test_t1_prerequisite_is_verified_and_required(tmp_path: Path) -> None:
    assert verify_ruo_t1(ROOT)["summary"] == {"passed": 74, "failed": 0, "total": 74}
    missing = tmp_path / "missing"; missing.mkdir()
    assert generate_runtime_profile(ROOT, tmp_path / "out", t1_directory=missing)["phase_status"] == "NOT_VALIDATED"


def test_native_core_build_and_unit_tests_pass() -> None:
    completed = subprocess.run(["cargo", "test", "--manifest-path", "NativeReasonUnitRuntime/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    # `cargo test` alone does not guarantee the `[[bin]]` target is built on a
    # fresh checkout; later tests load it directly from target/debug.
    built = subprocess.run(["cargo", "build", "--manifest-path", "NativeReasonUnitRuntime/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert built.returncode == 0, built.stderr


def test_native_types_are_compiled_and_safe_rust() -> None:
    source = (ROOT / "NativeReasonUnitRuntime/src/lib.rs").read_text(encoding="utf-8")
    assert all(name in source for name in NATIVE_TYPES)
    assert "unsafe {" not in source


def test_native_loader_exposes_stable_sorted_ids(generated: Path) -> None:
    binary = ROOT / "NativeReasonUnitRuntime/target/debug/reasonunit-runtime-native"
    result = json.loads(subprocess.run([str(binary), "load", str(generated / "fixtures/complete.ruo")], capture_output=True, text=True, check=True).stdout)
    assert result["ok"] and result["native_execution_provenance"] == PROFILE
    assert result["entity_ids"] == sorted(result["entity_ids"])
    assert all(":" in entity_id for entity_id in result["entity_ids"])


def test_python_writer_exponent_numbers_load_in_native_runtime(tmp_path: Path) -> None:
    logical = reference_object()
    numeric = next(
        item for item in logical["payloads"]
        if item["profile_id"] == "ruo.payload.numeric/1"
    )
    numeric["value"]["values"] = [1e-7, -2.5e-9, 3.25e20]
    target = tmp_path / "python-written-exponents.ruo"
    assert write_file(logical, target)["ok"]

    completed = subprocess.run(
        [
            "cargo", "run", "--offline", "--quiet",
            "--manifest-path", "NativeReasonUnitRuntime/Cargo.toml",
            "--bin", "reasonunit-runtime-native", "--", "load", str(target),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    result = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert result["ok"] and result["object_id"] == logical["object_identity"]["entity_id"]


def test_native_reader_rejects_tampered_raw_body(tmp_path: Path) -> None:
    target = tmp_path / "tampered.ruo"
    write_file(reference_object(), target)
    payload = target.read_bytes().replace(b"universal", b"UniversaL", 1)
    target.write_bytes(payload)
    binary = ROOT / "NativeReasonUnitRuntime/target/debug/reasonunit-runtime-native"
    completed = subprocess.run(
        [str(binary), "load", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    result = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert result["diagnostics"][0]["code"] == "RUO-N1-007"
    assert result["diagnostics"][0]["message"] == "record digest mismatch"


def test_cli_native_provenance_and_phase_json(generated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_run(["snapshot", str(generated / "fixtures/complete.ruo"), "--json"], ROOT) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["native_execution_provenance"] == PROFILE and result["snapshot_generation"] == 1


def test_phase_generates_54_artifacts_and_74_tests(generated: Path) -> None:
    assert len(CANONICAL_ARTIFACTS) == 54 and all((generated / name).is_file() for name in CANONICAL_ARTIFACTS)
    summary = json.loads((generated / "validation_summary.json").read_text())["data"]
    assert summary["summary"] == {"passed": 74, "failed": 0, "total": 74}
    assert summary["statuses"]["transition_decision"] == "PROCEED_TO_RUO-N2"


def test_invalid_fixture_coverage_and_atomicity(generated: Path) -> None:
    manifest = json.loads((generated / "invalid_fixture_manifest.json").read_text())["data"]
    atomicity = json.loads((generated / "transaction_atomicity_report.json").read_text())["data"]
    assert manifest["case_count"] == len(INVALID_CASES) == 26
    assert atomicity["partial_commit_count"] == 0 and atomicity["invalid_rollback"]


def test_artifact_envelopes_and_manifest_inventory(generated: Path) -> None:
    for path in generated.glob("*.json"):
        value = json.loads(path.read_text()); assert value["profile_version"] == PROFILE and set(value) == {"schema_version", "profile_version", "data"}
    manifest = json.loads((generated / "run_manifest.json").read_text())["data"]
    assert manifest["artifact_count"] == 54 and manifest["file_count"] == len(manifest["files"])


def test_three_run_determinism_and_offline_validation(generated: Path) -> None:
    assert validate_runtime_profile(ROOT, generated, verify_determinism=True)["ok"]
