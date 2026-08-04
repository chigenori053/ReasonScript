"""ReasonScript IDE V0.5 acceptance tests (Phase 5.7).

Fixes the acceptance matrix from the Phase 5 spec section 5.7.3 so that
"ReasonScript IDE V0.5" has a durable, checkable definition of done.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = REPO_ROOT / "apps" / "reasonscript-ide" / "ui"
UI_SRC = UI_ROOT / "src"
PLAYGROUND_FRONTEND = REPO_ROOT / "playground" / "frontend"
COMMANDS_DOC = REPO_ROOT / "docs" / "development" / "commands.md"
TEST_MATRIX_DOC = REPO_ROOT / "docs" / "development" / "test_matrix.md"
DEV_SCRIPT = REPO_ROOT / "scripts" / "dev.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_official_ide_ui_exists() -> None:
    assert (UI_SRC / "App.tsx").is_file()
    assert (UI_ROOT / "package.json").is_file()


def test_playground_frontend_does_not_exist() -> None:
    assert not PLAYGROUND_FRONTEND.exists()


def test_workspace_explorer_exists() -> None:
    assert (UI_SRC / "views" / "WorkspaceExplorerView.tsx").is_file()


def test_sample_browser_exists() -> None:
    assert (UI_SRC / "views" / "SampleBrowserView.tsx").is_file()
    assert (UI_SRC / "viewModels" / "sampleBrowser.ts").is_file()


def test_editor_state_model_exists() -> None:
    assert (UI_SRC / "viewModels" / "editorWorkspaceState.ts").is_file()


def test_workspace_diagnostics_model_exists() -> None:
    assert (UI_SRC / "viewModels" / "workspaceDiagnostics.ts").is_file()


def test_file_level_diagnostics_mapping_exists() -> None:
    assert (UI_SRC / "viewModels" / "fileDiagnosticsMapping.ts").is_file()


def test_stale_artifact_detection_exists() -> None:
    assert (UI_SRC / "viewModels" / "artifactFreshness.ts").is_file()


def test_project_validation_summary_exists() -> None:
    assert (UI_SRC / "viewModels" / "projectValidation.ts").is_file()


def test_problems_final_integration_exists() -> None:
    source = _read(UI_SRC / "views" / "StandardLayoutViews.tsx")
    assert "problemsScope" in source
    assert "filterByScope" in source


def test_output_final_integration_exists() -> None:
    source = _read(UI_SRC / "views" / "StandardLayoutViews.tsx")
    assert "Workspace / Project Validation Logs" in source


def test_artifacts_include_validation_report() -> None:
    source = _read(UI_SRC / "views" / "StandardLayoutViews.tsx")
    assert "project_validation.json" in source
    assert "artifact_freshness.json" in source


def test_commands_doc_points_to_official_ide() -> None:
    source = _read(COMMANDS_DOC)
    assert "apps/reasonscript-ide/ui" in source
    assert "physically removed" in source


def test_test_matrix_doc_points_to_official_ide() -> None:
    source = _read(TEST_MATRIX_DOC)
    assert "apps/reasonscript-ide/ui" in source


def test_dev_script_frontend_target_uses_official_ide_ui() -> None:
    source = _read(DEV_SCRIPT)
    assert "apps/reasonscript-ide/ui" in source
