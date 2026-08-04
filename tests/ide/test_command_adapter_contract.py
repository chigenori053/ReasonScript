from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
PLATFORM_DIR = UI_SRC / "platform"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_phase_4c_ide_command_definitions_include_required_commands():
    source = _read(PLATFORM_DIR / "types.ts")
    required = [
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

    for command in required:
        assert f'"{command}"' in source


def test_command_adapter_accepts_command_request_and_returns_command_result():
    source = _read(PLATFORM_DIR / "types.ts")

    assert "export interface CommandRequest" in source
    assert "command: IdeCommand" in source
    assert 'source?: "top_bar" | "shortcut" | "menu" | "panel" | "system"' in source
    assert "export interface CommandResult" in source
    assert "execute(request: CommandRequest): Promise<CommandResult>" in source


def test_browser_unsupported_command_result_keeps_command_name():
    source = _read(PLATFORM_DIR / "browserAdapter.ts")

    assert "createUnsupportedCommandAdapter" in source
    assert "command: request.command" in source
    assert "unsupportedPlatformError(`commands.${request.command}`)" in source


def test_top_bar_actions_execute_commands():
    source = _read(UI_SRC / "App.tsx")

    assert 'onSave={() => executeCommand("saveFile", "top_bar")}' in source
    assert 'onRun={() => executeCommand("runCurrentFile", "top_bar")}' in source
    assert 'onAnalyze={() => executeCommand("analyzeFile", "top_bar")}' in source
    assert 'onValidate={() => executeCommand("validateWorkspace", "top_bar")}' in source
    assert 'onAudit={() => executeCommand("auditProject", "top_bar")}' in source


def test_show_commands_switch_inspector_and_bottom_tabs():
    source = _read(UI_SRC / "App.tsx")

    for command, tab in [
        ("showPlan", "plan"),
        ("showSimulation", "simulation"),
        ("showKnowledge", "knowledge"),
        ("showArtifacts", "artifacts"),
        ("showProblems", "problems"),
        ("showOutput", "output"),
    ]:
        assert f'commandRegistry.register("{command}"' in source
        assert f'("{tab}")' in source
