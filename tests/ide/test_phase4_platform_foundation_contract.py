from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
PLATFORM = UI_SRC / "platform"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_platform_adapter_exposes_phase4_sub_adapters():
    source = _read(PLATFORM / "types.ts")

    assert "export interface PlatformAdapter" in source
    for field in [
        "environment: PlatformEnvironment",
        "workspace: WorkspaceAdapter",
        "artifacts: ArtifactAdapter",
        "commands: CommandAdapter",
        "settings: SettingsAdapter",
        "notifications: NotificationAdapter",
    ]:
        assert field in source


def test_phase4_command_surface_is_fixed():
    source = _read(PLATFORM / "types.ts")
    required_commands = [
        "openWorkspace",
        "refreshWorkspace",
        "saveFile",
        "analyzeFile",
        "runCurrentFile",
        "validateWorkspace",
        "auditProject",
        "showOverview",
        "showPlan",
        "showSimulation",
        "showKnowledge",
        "showArtifacts",
        "showProblems",
        "showOutput",
        "showLogs",
        "showTests",
        "clearOutput",
        "clearNotifications",
    ]

    for command in required_commands:
        assert f'"{command}"' in source


def test_required_artifact_names_are_analyze_result_backed():
    source = _read(PLATFORM / "browserAdapter.ts")
    required_artifacts = [
        "ast.json",
        "semantic_ast.json",
        "reason_ir.json",
        "execution_plan.json",
        "simulation.json",
        "knowledge.json",
        "diagnostics.json",
        "validation.json",
    ]

    assert "const ARTIFACT_FIELDS" in source
    assert "analyzeArtifactSource" in source
    for artifact in required_artifacts:
        assert f'fileName: "{artifact}"' in source


def test_required_settings_are_loaded_and_persisted_through_settings_adapter():
    app = _read(UI_SRC / "App.tsx")
    browser = _read(PLATFORM / "browserAdapter.ts")

    for key in [
        "compilerMode",
        "rightInspector.activeTab",
        "bottomToolWindow.activeTab",
    ]:
        assert f'platform.settings.get<string>("{key}")' in app
        assert f'platform.settings.set("{key}"' in app

    assert "window.localStorage.getItem" in browser
    assert "window.localStorage.setItem" in browser
    assert "createMemorySettingsAdapter()" in browser


def test_platform_error_vocabulary_and_path_policy_are_fixed():
    source = _read(PLATFORM / "types.ts")
    required_kinds = [
        "missing",
        "read_only",
        "permission_denied",
        "invalid_encoding",
        "path_traversal",
        "conflict",
        "unsupported",
        "network_error",
        "unknown",
    ]

    for kind in required_kinds:
        assert f'"{kind}"' in source

    assert 'path.includes("\\\\")' in source
    assert 'path.startsWith("/")' in source
    assert 'path.startsWith("../")' in source
    assert "/^[A-Za-z]:/.test(path)" in source
    assert 'part === ".."' in source


def test_backend_contract_entry_points_are_unchanged():
    bridge = _read(UI_SRC / "bridge.ts")
    browser = _read(PLATFORM / "browserAdapter.ts")

    assert 'fetch("/api/analyze"' in bridge
    assert "source_context: sourceContext" in bridge
    assert '"/api/workspace/list"' in browser
    assert '"/api/workspace/read"' in browser
    assert '"/api/workspace/save"' in browser
