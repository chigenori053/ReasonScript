"""Phase 4.5-C2-E sample selector final decision contract tests."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "sampleBrowser.ts"
APP = UI_SRC / "App.tsx"
BRIDGE = UI_SRC / "bridge.ts"
WORKSPACE_EXPLORER = UI_SRC / "views" / "WorkspaceExplorerView.tsx"
SAMPLE_BROWSER_VIEW = UI_SRC / "views" / "SampleBrowserView.tsx"
SAMPLE_LOGS_VIEW = UI_SRC / "views" / "SampleOperationLogsView.tsx"
SAMPLE_METADATA_VIEW = UI_SRC / "views" / "SampleMetadataView.tsx"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
FEATURE_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_migration_decision.md"
API_DOC = REPO_ROOT / "docs" / "development" / "legacy_api_retention_policy.md"
PLACEMENT_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_official_ide_placement.md"
MIGRATION_DOC = REPO_ROOT / "docs" / "development" / "sample_selector_final_decision_phase_4_5_c2_e.md"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "ide_phase_4_5_c2_e_sample_selector_final_decision.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _app_right_inspector_ids() -> list[str]:
    source = _read(APP)
    start = source.index("const rightInspectorTabs")
    end = source.index("  ];", start)
    return re.findall(r'id:\s*"([^"]+)"', source[start:end])


def test_sample_browser_view_model_file_exists() -> None:
    assert VIEW_MODEL.is_file()
    source = _read(VIEW_MODEL)
    for text in [
        "export type SampleBrowserStatus",
        "export type SampleLoadStatus",
        "export interface ReasonScriptSample",
        "export interface SampleBrowserViewModel",
        "buildSampleBrowserViewModel",
        "sampleBrowserIssuesAsPlatformDiagnostics",
    ]:
        assert text in source


def test_official_ide_includes_sample_browser_surface() -> None:
    source = _read(SAMPLE_BROWSER_VIEW) + _read(WORKSPACE_EXPLORER)
    for text in [
        "SampleBrowserView",
        "Examples",
        "Open Example",
        "data-sample-browser",
    ]:
        assert text in source


def test_examples_api_client_integration_exists_without_backend_contract_rewrite() -> None:
    source = _read(BRIDGE) + _read(APP) + _read(MIGRATION_DOC)
    assert '"/api/examples"' in source
    assert "fetchExamples" in source
    assert "without backend contract rewrite" in source.lower()
    assert "does not change backend request or" in source


def test_sample_browser_is_integrated_without_new_top_level_right_inspector_tab() -> None:
    assert _app_right_inspector_ids() == ["overview", "plan", "simulation", "knowledge", "artifacts"]
    source = _read(WORKSPACE_EXPLORER) + _read(PLACEMENT_DOC)
    assert "Workspace Explorer" in source
    assert "No new top-level right inspector tab is added." in _read(MIGRATION_DOC)


def test_sample_load_safety_policy_is_documented_and_implemented() -> None:
    source = _read(APP) + _read(MIGRATION_DOC)
    for text in [
        "Unsaved editor content blocks example loading.",
        "Sample source unavailable.",
        "Failed sample load must not mutate editor source.",
        "Unsaved editor content must not be silently overwritten.",
    ]:
        assert text in source


def test_sample_load_errors_are_routed_to_problems() -> None:
    source = _read(APP) + _read(VIEW_MODEL)
    assert "sampleBrowserIssuesAsPlatformDiagnostics" in source
    assert "sampleBrowserDiagnostics" in source
    assert "SAMPLE_FETCH_FAILED" in source
    assert "SAMPLE_LOAD_BLOCKED" in source
    assert 'setBottomToolTab("problems")' in source


def test_sample_load_logs_are_routed_to_output() -> None:
    source = _read(STANDARD_LAYOUT) + _read(SAMPLE_LOGS_VIEW) + _read(APP)
    assert "SampleOperationLogsView" in source
    assert "Sample Load Logs" in source
    for text in [
        "Examples fetch started.",
        "Examples fetch completed",
        "Example loaded:",
        "No sample operation logs.",
    ]:
        assert text in source


def test_sample_metadata_policy_is_documented_and_integrated() -> None:
    source = _read(STANDARD_LAYOUT) + _read(SAMPLE_METADATA_VIEW) + _read(MIGRATION_DOC)
    assert "SampleMetadataView" in source
    assert 'id: "samples"' in source
    assert "Sample Metadata" in source
    assert "raw sample metadata" in source.lower()


def test_missing_examples_state_has_fallback_empty_states() -> None:
    source = _read(SAMPLE_BROWSER_VIEW) + _read(MIGRATION_DOC)
    for text in [
        "No examples available.",
        "No sample selected.",
        "Sample source unavailable.",
        "Example loading failed.",
        "Examples unavailable.",
    ]:
        assert text in source


def test_legacy_feature_decision_doc_updates_sample_selector_to_migrated() -> None:
    source = _read(FEATURE_DOC)
    row = re.search(r"^\|\s*Sample selector\s*\|.*$", source, re.MULTILINE)
    assert row is not None
    assert "`MIGRATED`" in row.group(0)
    assert "REVIEWED - UPDATED THROUGH PHASE 4.5-D." in source
    assert "LEGACY PLAYGROUND FRONTEND REMOVED" in source
    assert "None. All previously deferred legacy UI features have been resolved." in source


def test_api_retention_policy_updates_examples_for_official_ide() -> None:
    source = _read(API_DOC)
    row = re.search(r"^\|\s*`/api/examples`\s*\|.*$", source, re.MULTILINE)
    assert row is not None
    assert "`KEEP_FOR_OFFICIAL_IDE`" in row.group(0)
    assert "Migrated in Phase 4.5-C2-E without backend contract rewrite." in row.group(0)


def test_docs_and_changelog_exist() -> None:
    for path in [PLACEMENT_DOC, MIGRATION_DOC, CHANGELOG]:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip()
    assert "Phase 4.5-C2-E" in _read(MIGRATION_DOC)
    assert "All legacy UI migration and decision blockers have been resolved." in _read(CHANGELOG)
