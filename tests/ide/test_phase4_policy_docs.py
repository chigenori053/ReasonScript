from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs" / "development"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


REQUIRED_DOCS = [
    "phase4_cross_platform_foundation.md",
    "browser_desktop_boundary.md",
    "platform_adapter_final_contract.md",
    "phase4_policy_index.md",
    "desktop_shell_deferred_policy.md",
]


def _read_doc(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_phase4_required_policy_docs_exist():
    for name in REQUIRED_DOCS:
        path = DOCS / name
        assert path.is_file(), name
        assert path.read_text(encoding="utf-8").strip()


def test_phase4_foundation_doc_covers_a_b_c_d_scope():
    source = _read_doc("phase4_cross_platform_foundation.md")

    for phrase in [
        "Phase 4-A introduced",
        "Phase 4-B moved workspace and artifact",
        "Phase 4-C moved IDE actions",
        "Phase 4-D does not add desktop features",
        "Backend contracts for `/api/analyze` and `/api/workspace/*` are unchanged",
    ]:
        assert phrase in source


def test_browser_desktop_boundary_doc_defers_native_shell_features():
    source = _read_doc("browser_desktop_boundary.md")

    for phrase in [
        "BrowserPlatformAdapter",
        "DesktopPlatformAdapter",
        "Native file dialogs are not implemented",
        "Native menus are not implemented",
        "Local process execution is not implemented",
        "`unsupported`",
    ]:
        assert phrase in source


def test_final_contract_doc_lists_required_contract_surface():
    source = _read_doc("platform_adapter_final_contract.md")

    for phrase in [
        "export interface PlatformAdapter",
        "WorkspaceAdapter",
        "ArtifactAdapter",
        "CommandAdapter",
        "SettingsAdapter",
        "NotificationAdapter",
        "saveFile",
        "analyzeFile",
        "ast.json",
        "diagnostics.json",
        "compilerMode",
        "rightInspector.activeTab",
        "bottomToolWindow.activeTab",
    ]:
        assert phrase in source


def test_policy_index_links_phase4_policy_documents():
    source = _read_doc("phase4_policy_index.md")

    for name in REQUIRED_DOCS:
        assert f"docs/development/{name}" in source

    for policy in [
        "cross_platform_path_policy.md",
        "workspace_adapter_migration.md",
        "artifact_adapter_migration.md",
        "command_adapter_contract.md",
        "settings_adapter_contract.md",
        "notification_adapter_contract.md",
    ]:
        assert policy in source


def test_desktop_shell_deferred_policy_lists_out_of_scope_items():
    source = _read_doc("desktop_shell_deferred_policy.md")

    for phrase in [
        "Desktop shell implementation is outside Phase 4-D",
        "Tauri integration",
        "Native file dialogs",
        "Native menu",
        "OS-level shortcut registration",
        "Local process execution",
        "Desktop native notifications",
    ]:
        assert phrase in source


def test_changelog_contains_phase4d_and_phase4_final_summary():
    source = CHANGELOG.read_text(encoding="utf-8")

    assert "ReasonScript IDE Phase 4-D - Cross-platform Policy, Tests, and Docs - 2026-07-01" in source
    assert "ReasonScript IDE Phase 4 - Cross-platform UI / Platform Adapter Foundation - 2026-07-01" in source
    assert "ReasonScript IDE Phase 4-D has been completed" in source
    assert "ReasonScript IDE Phase 4 has been completed" in source
    assert "VALIDATED" in source
