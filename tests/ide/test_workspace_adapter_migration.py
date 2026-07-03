from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"


def _read(path: str) -> str:
    return (UI_SRC / path).read_text(encoding="utf-8")


def test_workspace_explorer_does_not_call_workspace_endpoints_or_bridge():
    source = _read("views/WorkspaceExplorerView.tsx")

    assert "/api/workspace/list" not in source
    assert "/api/workspace/read" not in source
    assert "/api/workspace/save" not in source
    assert "openWorkspace" not in source
    assert "refreshWorkspace" not in source


def test_app_routes_workspace_workflows_through_platform_adapter():
    source = _read("App.tsx")

    assert "getPlatformAdapter()" in source
    assert "platform.workspace.listWorkspace" in source
    assert "platform.workspace.readFile" in source
    assert "platform.workspace.saveFile" in source
    assert "validateNormalizedRelativePath(wsStore.selectedPath)" in source


def test_analyze_current_file_validates_relative_path_before_source_context():
    source = _read("App.tsx")

    validation_index = source.index("validateNormalizedRelativePath(wsStore.selectedPath)")
    analyze_index = source.index("buildProjectState(")
    assert validation_index < analyze_index
    assert "dirty: source !== savedSource" in source


def test_browser_workspace_adapter_calls_existing_workspace_endpoints():
    source = _read("platform/browserAdapter.ts")

    assert '"/api/workspace/list"' in source
    assert '"/api/workspace/read"' in source
    assert '"/api/workspace/save"' in source
    assert "validateNormalizedRelativePath(request.relativePath)" in source
    assert "expected_version: request.expectedVersion" in source
