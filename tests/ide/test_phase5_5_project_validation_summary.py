"""Phase 5.5 project validation summary contract tests."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "projectValidation.ts"
SUMMARY_VIEW = UI_SRC / "views" / "ProjectValidationSummaryView.tsx"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_project_validation_model_matches_spec() -> None:
    source = _read(VIEW_MODEL)
    assert "export type ProjectValidationStatus" in source
    for status in ["valid", "warning", "invalid", "unavailable"]:
        assert f'"{status}"' in source
    assert "export interface ProjectValidationSummary" in source
    for field in [
        "status",
        "workspaceRoot",
        "validFileCount",
        "invalidFileCount",
        "ignoredFileCount",
        "diagnosticCount",
        "errorCount",
        "warningCount",
        "artifactFreshness",
        "canAnalyze",
        "canRun",
        "reason",
    ]:
        assert field in source


def test_build_function_exists() -> None:
    source = _read(VIEW_MODEL)
    assert "buildProjectValidationSummary" in source


def test_missing_workspace_produces_unavailable_status() -> None:
    source = _read(VIEW_MODEL)
    assert "if (!workspace)" in source
    assert '"unavailable"' in source


def test_overview_shows_project_validation_summary() -> None:
    layout_source = _read(STANDARD_LAYOUT)
    assert "ProjectValidationSummaryView" in layout_source
    assert "projectValidationSummary" in layout_source
    assert "project_validation.json" in layout_source


def test_app_wires_project_validation_summary() -> None:
    source = _read(APP)
    assert "buildProjectValidationSummary" in source
