"""Phase 5.4 stale artifact detection contract tests."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "artifactFreshness.ts"
SUMMARY_VIEW = UI_SRC / "views" / "ArtifactFreshnessSummaryView.tsx"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"

TRACKED_ARTIFACTS = ["surface_ast", "reason_ir", "execution_plan", "simulation", "knowledge"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_artifact_freshness_model_matches_spec() -> None:
    source = _read(VIEW_MODEL)
    assert "export type ArtifactFreshnessStatus" in source
    for status in ["fresh", "stale", "unavailable", "unknown"]:
        assert f'"{status}"' in source
    assert "export interface ArtifactFreshness" in source
    for field in ["artifactName", "status", "sourceHash", "artifactSourceHash", "generatedAt", "reason"]:
        assert field in source


def test_tracked_artifacts_present() -> None:
    source = _read(VIEW_MODEL)
    for artifact in TRACKED_ARTIFACTS:
        assert artifact in source


def test_build_function_exists() -> None:
    source = _read(VIEW_MODEL)
    assert "buildArtifactFreshness" in source


def test_overview_and_artifacts_show_freshness() -> None:
    layout_source = _read(STANDARD_LAYOUT)
    assert "ArtifactFreshnessSummaryView" in layout_source
    assert "artifactFreshnessVm" in layout_source
    assert "artifact_freshness.json" in layout_source


def test_app_recomputes_freshness_from_current_source() -> None:
    source = _read(APP)
    assert "buildArtifactFreshness(ps, source)" in source
