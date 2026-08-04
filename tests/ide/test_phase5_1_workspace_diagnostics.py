"""Phase 5.1 workspace diagnostics contract tests."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "workspaceDiagnostics.ts"
SUMMARY_VIEW = UI_SRC / "views" / "WorkspaceDiagnosticsSummaryView.tsx"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workspace_diagnostics_view_model_file_exists() -> None:
    assert VIEW_MODEL.is_file()
    source = _read(VIEW_MODEL)
    assert "export interface WorkspaceDiagnosticsViewModel" in source
    assert "buildWorkspaceDiagnosticsViewModel" in source
    assert "workspaceDiagnosticsAsPlatformDiagnostics" in source


def test_workspace_diagnostics_summary_view_exists() -> None:
    assert SUMMARY_VIEW.is_file()
    source = _read(SUMMARY_VIEW)
    assert "Workspace Diagnostics Summary" in source


def test_overview_integrates_workspace_diagnostics_summary() -> None:
    source = _read(STANDARD_LAYOUT)
    assert "WorkspaceDiagnosticsSummaryView" in source
    assert "workspaceDiagnosticsVm" in source


def test_app_wires_workspace_diagnostics_into_problems() -> None:
    source = _read(APP)
    assert "buildWorkspaceDiagnosticsViewModel" in source
    assert "workspaceDiagnosticsAsPlatformDiagnostics" in source
    assert "workspaceDiagnosticsVm" in source


def test_missing_workspace_state_does_not_crash() -> None:
    source = _read(VIEW_MODEL)
    assert "if (!workspace) return UNAVAILABLE;" in source
