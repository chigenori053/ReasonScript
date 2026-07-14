import json
import subprocess
import sys
from pathlib import Path

from toolchain.version_validation import validate_version

ROOT = Path(__file__).resolve().parents[2]


def test_release_metadata_is_consistent():
    payload = validate_version(ROOT)
    assert payload["schema_version"] == "reasonscript-version-validation/1.0"
    assert payload["status"] == "pass"
    assert [item["id"] for item in payload["checks"]] == [f"VER-{i:03d}" for i in range(1, 7)]


def test_hyphenated_project_and_artifact_resolution(tmp_path: Path):
    cli = ROOT / "reason"
    created = subprocess.run([str(cli), "init", "inference-validation"], cwd=tmp_path, text=True, capture_output=True)
    assert created.returncode == 0, created.stderr
    assert "Package identifier: inference_validation" in created.stdout
    project = tmp_path / "inference-validation"
    source = (project / "src/main.rsn").read_text(encoding="utf-8")
    assert "package inference_validation" in source
    generated = subprocess.run([str(cli), "artifacts", "src/main.rsn"], cwd=project, text=True, capture_output=True)
    assert generated.returncode == 0, generated.stderr
    assert (project / "artifacts/artifact_manifest.json").is_file()
    assert str(project / "artifacts") in generated.stdout


def test_explicit_artifact_output_overrides_manifest(tmp_path: Path):
    cli = ROOT / "reason"
    subprocess.run([str(cli), "init", "demo"], cwd=tmp_path, check=True, capture_output=True)
    project = tmp_path / "demo"
    generated = subprocess.run([str(cli), "artifacts", "src/main.rsn", "--out", "build/output"], cwd=project, text=True, capture_output=True)
    assert generated.returncode == 0, generated.stderr
    assert (project / "build/output/artifact_manifest.json").is_file()


def test_version_validate_cli_json():
    result = subprocess.run([str(ROOT / "reason"), "version-validate", "--json"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"
