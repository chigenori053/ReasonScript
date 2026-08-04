from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
SHORTCUTS = UI_SRC / "platform" / "shortcuts.ts"
APP = UI_SRC / "App.tsx"


def test_shortcut_bindings_reference_commands():
    source = SHORTCUTS.read_text(encoding="utf-8")

    assert "export interface IdeShortcutBinding" in source
    assert 'command: "saveFile"' in source
    assert 'command: "analyzeFile"' in source
    assert 'command: "showProblems"' in source
    assert 'mac: "Cmd+S"' in source
    assert 'windows: "Ctrl+Enter"' in source
    assert 'linux: "Ctrl+Shift+M"' in source


def test_keydown_listener_executes_commands_not_direct_handlers():
    source = APP.read_text(encoding="utf-8")

    assert 'executeCommand("analyzeFile", "shortcut")' in source
    assert 'executeCommand("saveFile", "shortcut")' in source
    assert 'executeCommand("showProblems", "shortcut")' in source
