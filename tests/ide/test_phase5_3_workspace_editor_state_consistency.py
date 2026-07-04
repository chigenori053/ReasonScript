"""Phase 5.3 workspace/editor state consistency contract tests."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "editorWorkspaceState.ts"
WORKSPACE_EXPLORER = UI_SRC / "views" / "WorkspaceExplorerView.tsx"
APP = UI_SRC / "App.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_editor_source_kind_model_matches_spec() -> None:
    source = _read(VIEW_MODEL)
    assert "export type EditorSourceKind" in source
    for kind in ["workspace_file", "sample", "unsaved", "missing"]:
        assert kind in source
    assert "export interface EditorWorkspaceState" in source
    for field in ["sourceKind", "relativePath", "sampleId", "dirty", "sourceHash", "selectedFileExists", "lastSavedHash"]:
        assert field in source


def test_derive_function_and_hash_helper_exist() -> None:
    source = _read(VIEW_MODEL)
    assert "deriveEditorWorkspaceState" in source
    assert "hashSource" in source


def test_missing_selected_file_is_detected() -> None:
    source = _read(VIEW_MODEL)
    assert '"missing"' in source
    assert "selectedFileExists" in source


def test_workspace_explorer_shows_source_kind_and_dirty_state() -> None:
    source = _read(WORKSPACE_EXPLORER)
    assert "editorSourceKindLabel" in source
    assert "editorWorkspaceState" in source
    assert "dirty" in source


def test_app_derives_editor_workspace_state_on_selection_and_sample_changes() -> None:
    source = _read(APP)
    assert "deriveEditorWorkspaceState" in source
    assert "editorWorkspaceState" in source
