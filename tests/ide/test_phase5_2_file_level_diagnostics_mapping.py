"""Phase 5.2 file-level diagnostics mapping contract tests."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "fileDiagnosticsMapping.ts"
WORKSPACE_EXPLORER = UI_SRC / "views" / "WorkspaceExplorerView.tsx"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_diagnostic_model_matches_spec() -> None:
    source = _read(VIEW_MODEL)
    assert "export type IdeDiagnosticSeverity" in source
    assert "export interface IdeSourceRange" in source
    assert "export interface IdeDiagnostic" in source
    for field in ["startLine", "startColumn", "endLine", "endColumn"]:
        assert field in source
    for field in ["id", "severity", "code", "message", "source", "relativePath", "sourceRange", "stage", "evidence"]:
        assert field in source


def test_mapping_functions_exist() -> None:
    source = _read(VIEW_MODEL)
    assert "buildFileDiagnosticsMapping" in source
    assert "filterByScope" in source
    assert "severityBadgeForPath" in source
    assert "UNKNOWN_PATH_GROUP" in source


def test_workspace_explorer_shows_diagnostic_badges() -> None:
    source = _read(WORKSPACE_EXPLORER)
    assert "severityBadgeForPath" in source
    assert "diagnosticsMapping" in source


def test_problems_tab_supports_scope_filter() -> None:
    source = _read(STANDARD_LAYOUT)
    assert "filterByScope" in source
    assert "DiagnosticScope" in source
    assert "problemsScope" in source


def test_app_wires_file_diagnostics_mapping() -> None:
    source = _read(APP)
    assert "buildFileDiagnosticsMapping" in source
    assert "fileDiagnosticsMappingForExplorer" in source
