from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "platform"


def _read(name: str) -> str:
    return (PLATFORM / name).read_text(encoding="utf-8")


def test_browser_adapter_has_browser_first_capability_flags():
    source = _read("browserAdapter.ts")

    assert 'kind: "browser"' in source
    assert 'os: "unknown"' in source
    assert "supportsLocalFilesystem: false" in source
    assert "supportsNativeDialogs: false" in source
    assert "supportsNativeMenu: false" in source
    assert "supportsProcessExecution: false" in source


def test_browser_adapter_uses_backend_workspace_and_analyze_artifacts():
    source = _read("browserAdapter.ts")

    assert 'postJson<{' in source
    assert '"/api/workspace/list"' in source
    assert '"/api/workspace/read"' in source
    assert '"/api/workspace/save"' in source
    assert "setBrowserAnalyzeArtifactSource" in source
    assert "createBrowserArtifactAdapter" in source


def test_desktop_adapter_is_conservative_stub():
    source = _read("desktopAdapter.ts")

    assert 'kind: "desktop"' in source
    assert 'os: "unknown"' in source
    assert "supportsLocalFilesystem: false" in source
    assert "supportsNativeDialogs: false" in source
    assert "supportsNativeMenu: false" in source
    assert "supportsProcessExecution: false" in source
    assert "createUnsupportedWorkspaceAdapter()" in source
    assert "createUnsupportedArtifactAdapter()" in source
    assert "createUnsupportedCommandAdapter()" in source


def test_unsupported_stub_operations_preserve_unsupported_error_kind():
    browser = _read("browserAdapter.ts")
    types = _read("types.ts")

    assert "createUnsupportedWorkspaceAdapter" in browser
    assert "createUnsupportedArtifactAdapter" in browser
    assert "createUnsupportedCommandAdapter" in browser
    assert 'createPlatformError("unsupported"' in types
    assert '"unsupported"' in types
    assert "Unsupported platform operation" in types


def test_notification_mapping_matches_phase4_policy():
    source = _read("browserAdapter.ts")

    for mapping in [
        'missing: "warning"',
        'read_only: "warning"',
        'permission_denied: "error"',
        'invalid_encoding: "error"',
        'path_traversal: "error"',
        'conflict: "warning"',
        'unsupported: "warning"',
        'network_error: "error"',
        'unknown: "error"',
    ]:
        assert mapping in source

    assert "export function notifyPlatformError" in source
    assert "try {" in source
    assert 'console.error("Notification failed."' in source
