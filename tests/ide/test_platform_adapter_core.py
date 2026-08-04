from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_DIR = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "platform"


def _read(name: str) -> str:
    return (PLATFORM_DIR / name).read_text(encoding="utf-8")


def test_platform_core_files_exist():
    assert (PLATFORM_DIR / "types.ts").is_file()
    assert (PLATFORM_DIR / "browserAdapter.ts").is_file()
    assert (PLATFORM_DIR / "desktopAdapter.ts").is_file()
    assert (PLATFORM_DIR / "index.ts").is_file()


def test_platform_types_define_core_contracts():
    source = _read("types.ts")

    assert "export interface PlatformAdapter" in source
    assert "export interface PlatformEnvironment" in source
    assert "export type PlatformErrorKind" in source
    assert "export type NormalizedRelativePath = string" in source
    assert "export interface WorkspaceAdapter" in source
    assert "export interface ArtifactAdapter" in source
    assert "export interface CommandAdapter" in source
    assert "export interface SettingsAdapter" in source
    assert "export interface NotificationAdapter" in source


def test_browser_and_desktop_environment_contracts_are_explicit():
    browser = _read("browserAdapter.ts")
    desktop = _read("desktopAdapter.ts")

    assert 'kind: "browser"' in browser
    assert "supportsLocalFilesystem: false" in browser
    assert "supportsNativeDialogs: false" in browser
    assert 'kind: "desktop"' in desktop
    assert "supportsLocalFilesystem: false" in desktop
    assert "supportsNativeDialogs: false" in desktop


def test_unsupported_operations_return_unsupported_platform_error():
    browser = _read("browserAdapter.ts")
    desktop = _read("desktopAdapter.ts")

    assert "unsupportedPlatformError" in browser
    assert 'createPlatformError("unsupported"' in _read("types.ts")
    assert "createUnsupportedWorkspaceAdapter()" in desktop
    assert "createUnsupportedArtifactAdapter()" in desktop
    assert "createUnsupportedCommandAdapter()" in desktop


def test_active_adapter_resolver_defaults_to_browser_adapter():
    source = _read("index.ts")

    assert "export function getPlatformAdapter()" in source
    assert "createBrowserPlatformAdapter()" in source


def test_normalized_relative_path_policy_is_represented():
    source = _read("types.ts")

    assert "isNormalizedRelativePath" in source
    assert 'path.includes("\\\\")' in source
    assert 'path.startsWith("/")' in source
    assert 'path.startsWith("../")' in source
    assert "path_traversal" in source
