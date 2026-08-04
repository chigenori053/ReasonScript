from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "canonical_fixtures/visualization_runtime/person_structure.json"


def reason(*args: str) -> tuple[int, dict]:
    completed = subprocess.run([str(ROOT / "reason"), "visualization", *args, "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
    return completed.returncode, json.loads(completed.stdout)


def test_project_person_structure_emits_semantic_artifacts(tmp_path: Path) -> None:
    status, result = reason("project", str(FIXTURE), "--output", str(tmp_path))
    assert status == 0, result
    assert result["scene_id"] == "scene:person-structure:fixture-v1"
    expected = {"visualization_manifest.json", "visualization_source.json", "visualization_scene.json", "visualization_render_plan.json", "visualization_evidence.json", "visualization_trace.json", "visualization_validation.json", "visualization_run_summary.json", "scene.svg"}
    assert expected == {path.name for path in tmp_path.iterdir()}
    scene = json.loads((tmp_path / "visualization_scene.json").read_text(encoding="utf-8"))
    assert scene["schema_version"] == "reasonscript-semantic-visualization-ir/0.1"
    assert scene["objects"][3]["epistemic_state"] == "inferred"
    svg = (tmp_path / "scene.svg").read_text(encoding="utf-8")
    assert "Left Arm" in svg and "stroke-dasharray=\"6 3\"" in svg


def test_project_is_deterministic_and_phase_validates(tmp_path: Path) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    assert reason("project", str(FIXTURE), "--output", str(first))[0] == 0
    assert reason("project", str(FIXTURE), "--output", str(second))[0] == 0
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {path.name: path.read_bytes() for path in second.iterdir()}
    status, result = reason("validate-phase", "--output", str(first))
    assert status == 0, result
    assert result["phase_status"] == "VALIDATED"


def test_project_vision_observation(tmp_path: Path) -> None:
    fixture = ROOT / "canonical_fixtures/vision_runtime/solar_observation.json"
    status, result = reason("project-vision", str(fixture), "--output", str(tmp_path))
    assert status == 0, result
    scene = json.loads((tmp_path / "visualization_scene.json").read_text(encoding="utf-8"))
    assert scene["source"]["source_profile"] == "reasonscript-vision-observation/0.1"
    assert scene["objects"]
