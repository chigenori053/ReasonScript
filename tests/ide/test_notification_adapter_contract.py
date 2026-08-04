from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
TYPES = UI_SRC / "platform" / "types.ts"
BROWSER = UI_SRC / "platform" / "browserAdapter.ts"
APP = UI_SRC / "App.tsx"


def test_notification_adapter_accepts_options():
    source = TYPES.read_text(encoding="utf-8")

    assert "export interface NotificationOptions" in source
    assert "info(message: string, options?: NotificationOptions): void" in source
    assert "warning(message: string, options?: NotificationOptions): void" in source
    assert "error(message: string, options?: NotificationOptions): void" in source


def test_platform_error_notification_mapping_is_defined():
    source = BROWSER.read_text(encoding="utf-8")

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


def test_command_failures_route_to_notifications():
    source = APP.read_text(encoding="utf-8")

    assert "notifyPlatformError(platform.notifications, result.error)" in source
    assert "platform.notifications.error" in source
    assert "platform.notifications.warning" in source
