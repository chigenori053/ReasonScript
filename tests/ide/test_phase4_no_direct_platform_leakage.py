from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
ADAPTER_ALLOWLIST = {
    UI_SRC / "platform" / "browserAdapter.ts",
}


def _source_files() -> list[Path]:
    return sorted(
        path
        for path in UI_SRC.rglob("*")
        if path.suffix in {".ts", ".tsx"}
    )


def test_workspace_endpoint_fetches_are_confined_to_browser_adapter():
    endpoints = [
        "/api/workspace/list",
        "/api/workspace/read",
        "/api/workspace/save",
    ]
    offenders: list[str] = []

    for path in _source_files():
        source = path.read_text(encoding="utf-8")
        for endpoint in endpoints:
            if endpoint in source and path not in ADAPTER_ALLOWLIST:
                offenders.append(f"{path.relative_to(REPO_ROOT)} contains {endpoint}")

    assert offenders == []


def test_workspace_ui_uses_platform_workspace_adapter():
    app = (UI_SRC / "App.tsx").read_text(encoding="utf-8")
    explorer = (UI_SRC / "views" / "WorkspaceExplorerView.tsx").read_text(encoding="utf-8")

    assert "platform.workspace.listWorkspace" in app
    assert "platform.workspace.readFile" in app
    assert "platform.workspace.saveFile" in app
    assert "/api/workspace/" not in explorer


def test_artifacts_inspector_uses_artifact_adapter_for_artifact_content():
    source = (UI_SRC / "views" / "StandardLayoutViews.tsx").read_text(encoding="utf-8")

    assert "getPlatformAdapter().artifacts" in source
    assert "adapter.getArtifactIndex({})" in source
    assert "adapter.readArtifact({ fileName: descriptor.fileName })" in source
    assert 'artifactContent["ast.json"]' in source
    assert 'artifactContent["reason_ir.json"]' in source


def test_top_bar_shortcuts_and_panel_switching_emit_commands():
    app = (UI_SRC / "App.tsx").read_text(encoding="utf-8")

    for command in [
        "saveFile",
        "runCurrentFile",
        "analyzeFile",
        "validateWorkspace",
        "auditProject",
    ]:
        assert f'executeCommand("{command}", "top_bar")' in app

    for command in ["saveFile", "analyzeFile", "showProblems"]:
        assert f'executeCommand("{command}", "shortcut")' in app

    for command in [
        "showOverview",
        "showPlan",
        "showSimulation",
        "showKnowledge",
        "showArtifacts",
        "showProblems",
        "showOutput",
        "showLogs",
        "showTests",
    ]:
        assert f'commandRegistry.register("{command}"' in app


def test_local_storage_access_is_confined_to_settings_adapter():
    offenders: list[str] = []

    for path in _source_files():
        source = path.read_text(encoding="utf-8")
        if "localStorage" in source and path != UI_SRC / "platform" / "browserAdapter.ts":
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
