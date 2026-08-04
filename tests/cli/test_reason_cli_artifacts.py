from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "scripts" / "dev.py"
VALID = REPO_ROOT / "examples" / "v0_5" / "002_single_calculation.rsn"
EXPECTED = {
    "language_surface_ast.json",
    "surface_ast.json",
    "semantic_ast.json",
    "reason_ir.json",
    "execution_plan.json",
    "simulation.json",
    "knowledge.json",
    "diagnostics.json",
    "diagnostics_summary.json",
    "validation.json",
    "project_state.json",
    "artifact_manifest.json",
    "artifact_summary.json",
}


def test_reason_artifacts_writes_stable_filenames(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(DEV), "reason", "artifacts", str(VALID), "--out", str(tmp_path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert {path.name for path in tmp_path.iterdir()} == EXPECTED
    project_state = json.loads((tmp_path / "project_state.json").read_text(encoding="utf-8"))
    assert project_state["version"] == "1.0"
    assert project_state["schema"] == "reasonscript-project-state/0.5"
    assert project_state["data"]["ok"] is True
    diagnostics = json.loads((tmp_path / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["version"] == "1.0"
    assert diagnostics["data"]["diagnostics"] == []
