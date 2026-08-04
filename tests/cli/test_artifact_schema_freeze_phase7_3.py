from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from toolchain.artifacts import (
    ARTIFACT_VERSION,
    artifact_envelope,
    stable_json,
    validate_artifact_directory,
    write_artifact_directory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "scripts" / "dev.py"
REASON = REPO_ROOT / "reason"
VALID = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"


def _codes(document: dict[str, object]) -> set[str]:
    diagnostics = document.get("diagnostics")
    assert isinstance(diagnostics, list)
    return {str(item["code"]) for item in diagnostics if isinstance(item, dict)}


def test_artifact_envelope_contains_required_metadata() -> None:
    artifact = artifact_envelope("reason_ir.json", {"modules": []}, generator="test", language_version="0.5")

    assert artifact["version"] == ARTIFACT_VERSION
    assert artifact["schema"] == "reason-ir/0.5"
    assert artifact["generator"] == "test"
    assert artifact["generated_at"] == "1970-01-01T00:00:00Z"
    assert artifact["language_version"] == "0.5"
    assert artifact["data"] == {"modules": []}


def test_artifact_directory_writes_manifest_summary_and_stable_json(tmp_path: Path) -> None:
    result = write_artifact_directory(
        tmp_path,
        {"reason_ir.json": {"modules": []}, "execution_plan.json": {"steps": []}},
        generator="test",
        language_version="0.5",
    )

    manifest = json.loads(tmp_path.joinpath("artifact_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads(tmp_path.joinpath("artifact_summary.json").read_text(encoding="utf-8"))
    assert result["artifacts"] == ["artifact_manifest.json", "artifact_summary.json", "execution_plan.json", "reason_ir.json"]
    assert manifest["artifact_version"] == "1.0"
    assert manifest["artifacts"] == ["execution_plan.json", "reason_ir.json"]
    assert summary["artifact_count"] == 2
    assert tmp_path.joinpath("reason_ir.json").read_text(encoding="utf-8") == stable_json(
        json.loads(tmp_path.joinpath("reason_ir.json").read_text(encoding="utf-8"))
    )


def test_reason_artifacts_cli_produces_canonical_layout(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(DEV), "reason", "artifacts", str(VALID), "--out", str(tmp_path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    filenames = {path.name for path in tmp_path.iterdir()}
    manifest = json.loads(tmp_path.joinpath("artifact_manifest.json").read_text(encoding="utf-8"))
    expected = {
        "artifact_manifest.json",
        "artifact_summary.json",
        "diagnostics.json",
        "diagnostics_summary.json",
        "language_surface_ast.json",
        "semantic_ast.json",
        "reason_ir.json",
        "execution_plan.json",
        "simulation.json",
        "knowledge.json",
        "validation.json",
    }
    assert result.returncode == 0
    assert expected <= filenames
    assert manifest["generator"] == "reason-cli"
    assert "language_surface_ast.json" in manifest["artifacts"]
    assert validate_artifact_directory(tmp_path)["diagnostics"] == []


def test_reason_export_manifest_and_validate_artifacts_commands(tmp_path: Path) -> None:
    export = subprocess.run(
        [sys.executable, str(DEV), "reason", "export", str(VALID), "--out", str(tmp_path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    manifest = subprocess.run(
        [sys.executable, str(DEV), "reason", "manifest", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    validation = subprocess.run(
        [sys.executable, str(DEV), "reason", "validate-artifacts", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    manifest_payload = json.loads(manifest.stdout)
    validation_payload = json.loads(validation.stdout)
    assert export.returncode == 0
    assert manifest.returncode == 0
    assert validation.returncode == 0
    assert manifest_payload["schema"] == "reasonscript-artifact-manifest/1.0"
    assert validation_payload["diagnostics"] == []


def test_workspace_index_cli_produces_artifact_manifest_and_summary(tmp_path: Path) -> None:
    tmp_path.joinpath("reason.toml").write_text(
        'name = "Example"\nversion = "0.5.0"\nlanguage = "0.5"\nworkspace = "1.0"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(REASON), "index", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    manifest = json.loads(tmp_path.joinpath("artifacts", "artifact_manifest.json").read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert "artifact_manifest.json" in payload["artifacts"]
    assert "artifact_summary.json" in payload["artifacts"]
    assert manifest["generator"] == "reason-workspace"
    assert validate_artifact_directory(tmp_path / "artifacts")["diagnostics"] == []


def test_artifact_validation_rules_ar_001_through_ar_010(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"
    assert "AR-010" in _codes(validate_artifact_directory(missing_dir))

    empty = tmp_path / "empty"
    empty.mkdir()
    assert "AR-001" in _codes(validate_artifact_directory(empty, expected=("reason_ir.json",)))
    assert "AR-009" in _codes(validate_artifact_directory(empty))

    invalid_json = tmp_path / "invalid_json"
    invalid_json.mkdir()
    invalid_json.joinpath("artifact_manifest.json").write_text("{bad", encoding="utf-8")
    assert "AR-002" in _codes(validate_artifact_directory(invalid_json))

    missing_schema = tmp_path / "missing_schema"
    missing_schema.mkdir()
    missing_schema.joinpath("reason_ir.json").write_text(stable_json({"version": "1.0", "generator": "x", "generated_at": "x"}), encoding="utf-8")
    missing_schema.joinpath("artifact_manifest.json").write_text(stable_json({"artifact_version": "1.0", "artifacts": ["reason_ir.json"]}), encoding="utf-8")
    assert "AR-003" in _codes(validate_artifact_directory(missing_schema))

    unsupported_schema = tmp_path / "unsupported_schema"
    write_artifact_directory(unsupported_schema, {"reason_ir.json": {}}, generator="test", language_version="0.5")
    value = json.loads(unsupported_schema.joinpath("reason_ir.json").read_text(encoding="utf-8"))
    value["schema"] = "unknown/9.9"
    unsupported_schema.joinpath("reason_ir.json").write_text(stable_json(value), encoding="utf-8")
    assert "AR-004" in _codes(validate_artifact_directory(unsupported_schema))

    missing_metadata = tmp_path / "missing_metadata"
    missing_metadata.mkdir()
    missing_metadata.joinpath("reason_ir.json").write_text(stable_json({"schema": "reason-ir/0.5"}), encoding="utf-8")
    missing_metadata.joinpath("artifact_manifest.json").write_text(stable_json({"artifact_version": "1.0", "artifacts": ["reason_ir.json"]}), encoding="utf-8")
    assert "AR-005" in _codes(validate_artifact_directory(missing_metadata))

    nondeterministic = tmp_path / "nondeterministic"
    write_artifact_directory(nondeterministic, {"reason_ir.json": {}}, generator="test", language_version="0.5")
    nondeterministic.joinpath("reason_ir.json").write_text('{"schema":"reason-ir/0.5","version":"1.0","generator":"x","generated_at":"x","data":{}}\n', encoding="utf-8")
    assert "AR-006" in _codes(validate_artifact_directory(nondeterministic))

    broken_reference = tmp_path / "broken_reference"
    broken_reference.mkdir()
    broken_reference.joinpath("artifact_manifest.json").write_text(stable_json({"artifact_version": "1.0", "artifacts": ["missing.json"]}), encoding="utf-8")
    assert "AR-007" in _codes(validate_artifact_directory(broken_reference))

    duplicate = tmp_path / "duplicate"
    duplicate.mkdir()
    duplicate.joinpath("artifact_manifest.json").write_text(stable_json({"artifact_version": "1.0", "artifacts": ["a.json", "a.json"]}), encoding="utf-8")
    assert "AR-008" in _codes(validate_artifact_directory(duplicate))
