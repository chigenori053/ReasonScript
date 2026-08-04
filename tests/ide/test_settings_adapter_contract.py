from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
TYPES = UI_SRC / "platform" / "types.ts"
BROWSER = UI_SRC / "platform" / "browserAdapter.ts"
APP = UI_SRC / "App.tsx"


def test_setting_keys_include_phase_4c_keys():
    source = TYPES.read_text(encoding="utf-8")

    for key in [
        "compilerMode",
        "rightInspector.activeTab",
        "bottomToolWindow.activeTab",
        "bottomToolWindow.visible",
        "layout.leftPaneWidth",
        "layout.rightPaneWidth",
        "layout.bottomPaneHeight",
        "workspace.lastRoot",
    ]:
        assert f'"{key}"' in source


def test_browser_settings_adapter_uses_local_storage_with_memory_fallback():
    source = BROWSER.read_text(encoding="utf-8")

    assert 'const SETTINGS_PREFIX = "reasonscript.ide."' in source
    assert "createBrowserSettingsAdapter" in source
    assert "window.localStorage.getItem" in source
    assert "window.localStorage.setItem" in source
    assert "createMemorySettingsAdapter()" in source
    assert "return memory" in source


def test_app_persists_compiler_mode_and_active_tabs():
    source = APP.read_text(encoding="utf-8")

    assert 'platform.settings.get<string>("compilerMode")' in source
    assert 'platform.settings.get<string>("rightInspector.activeTab")' in source
    assert 'platform.settings.get<string>("bottomToolWindow.activeTab")' in source
    assert 'platform.settings.set("compilerMode", mode)' in source
    assert 'platform.settings.set("rightInspector.activeTab", tabId)' in source
    assert 'platform.settings.set("bottomToolWindow.activeTab", tabId)' in source
