"""Phase 4.5-C2-D audit and language audit matrix migration contract tests."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "languageAudit.ts"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"
BRIDGE = UI_SRC / "bridge.ts"
SUMMARY_VIEW = UI_SRC / "views" / "LanguageAuditSummaryView.tsx"
MATRIX_VIEW = UI_SRC / "views" / "LanguageAuditMatrixView.tsx"
LOGS_VIEW = UI_SRC / "views" / "LanguageAuditLogsView.tsx"
ARTIFACTS_VIEW = UI_SRC / "views" / "LanguageAuditArtifactsView.tsx"
FEATURE_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_migration_decision.md"
API_DOC = REPO_ROOT / "docs" / "development" / "legacy_api_retention_policy.md"
PLACEMENT_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_official_ide_placement.md"
MIGRATION_DOC = REPO_ROOT / "docs" / "development" / "audit_language_matrix_migration_phase_4_5_c2_d.md"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "ide_phase_4_5_c2_d_audit_language_matrix_migration.md"

MIGRATED_FEATURES = ["Audit", "Language audit matrix"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _app_right_inspector_ids() -> list[str]:
    source = _read(APP)
    start = source.index("const rightInspectorTabs")
    end = source.index("  ];", start)
    return re.findall(r'id:\s*"([^"]+)"', source[start:end])


def test_language_audit_view_model_file_exists() -> None:
    assert VIEW_MODEL.is_file()
    source = _read(VIEW_MODEL)
    for text in [
        "export type AuditStatus",
        "export type AuditItemStatus",
        "export interface LanguageAuditViewModel",
        "buildLanguageAuditViewModel",
        "languageAuditIssuesAsPlatformDiagnostics",
    ]:
        assert text in source


def test_official_ide_includes_audit_and_matrix_surfaces() -> None:
    source = _read(SUMMARY_VIEW) + _read(MATRIX_VIEW)
    for text in [
        "Audit Summary",
        "Run Audit",
        "Language Audit Matrix",
        "data-language-audit-summary",
        "data-language-audit-matrix",
    ]:
        assert text in source


def test_overview_integration_includes_audit_summary() -> None:
    source = _read(STANDARD_LAYOUT) + _read(SUMMARY_VIEW)
    assert "LanguageAuditSummaryView" in source
    for text in ["Connected items", "Missing items", "Warning items", "Error items", "Last audit run"]:
        assert text in source


def test_tests_integration_includes_language_audit_matrix() -> None:
    source = _read(STANDARD_LAYOUT) + _read(MATRIX_VIEW)
    assert "LanguageAuditMatrixView" in source
    assert 'id: "tests"' in source
    for text in ["Category", "Feature", "Expected", "Actual", "Status"]:
        assert text in source


def test_problems_integration_includes_audit_issues() -> None:
    source = _read(APP) + _read(VIEW_MODEL)
    assert "languageAuditIssuesAsPlatformDiagnostics" in source
    assert "languageAuditDiagnostics" in source
    assert "AUDIT_STALE" in source
    assert "AUDIT_EXPORT_FAILED" in source


def test_output_integration_includes_audit_operation_logs() -> None:
    source = _read(STANDARD_LAYOUT) + _read(LOGS_VIEW) + _read(APP)
    assert "LanguageAuditLogsView" in source
    assert "Audit Operation Logs" in source
    for text in ["Audit started.", "Audit completed", "Audit export started.", "No audit operation logs."]:
        assert text in source


def test_artifacts_integration_includes_raw_audit_report_and_matrix_json() -> None:
    source = _read(STANDARD_LAYOUT) + _read(ARTIFACTS_VIEW)
    assert "LanguageAuditArtifactsView" in source
    assert 'id: "audit"' in source
    for text in ["Raw Audit Report", "Raw Language Audit Matrix JSON", "Audit Export Result"]:
        assert text in source


def test_audit_export_and_freshness_policies_are_documented() -> None:
    source = _read(MIGRATION_DOC)
    assert "Audit Export Policy" in source
    assert "Audit Freshness Policy" in source
    assert "/api/language-audit/export" in source
    assert "stale audit result remains visible" in source.lower()


def test_standard_layout_top_level_right_inspector_tabs_remain_unchanged() -> None:
    assert _app_right_inspector_ids() == ["overview", "plan", "simulation", "knowledge", "artifacts"]


def test_language_audit_api_integration_exists_without_backend_contract_rewrite() -> None:
    source = _read(BRIDGE) + _read(APP) + _read(MIGRATION_DOC)
    assert '"/api/language-audit"' in source
    assert '"/api/language-audit/export"' in source
    assert "runLanguageAudit" in source
    assert "exportLanguageAudit" in source
    assert "without backend contract rewrite" in source.lower()


def test_missing_audit_state_has_fallback_empty_states() -> None:
    source = _read(SUMMARY_VIEW) + _read(MATRIX_VIEW) + _read(LOGS_VIEW) + _read(ARTIFACTS_VIEW)
    for text in [
        "No language audit has been run.",
        "No language audit matrix available.",
        "No audit operation logs.",
        "Language audit unavailable.",
        "Audit export unavailable.",
    ]:
        assert text in source


def test_legacy_feature_decision_docs_updated_to_migrated() -> None:
    source = _read(FEATURE_DOC)
    for feature in MIGRATED_FEATURES:
        row = re.search(rf"^\|\s*{re.escape(feature)}\s*\|.*$", source, re.MULTILINE)
        assert row is not None, feature
        assert "`MIGRATED`" in row.group(0)
    assert "REVIEWED - UPDATED THROUGH PHASE 4.5-D." in source
    assert "LEGACY PLAYGROUND FRONTEND REMOVED" in source


def test_final_recommendation_text_is_updated_for_post_c2_d_tracking() -> None:
    source = _read(FEATURE_DOC)
    assert "Legacy Playground frontend has been physically removed." in source
    assert "Phase 5 - Workspace Diagnostics & Project Validation" in source


def test_api_retention_policy_updated_for_language_audit() -> None:
    source = _read(API_DOC)
    audit_row = re.search(r"^\|\s*`/api/language-audit`\s*\|.*$", source, re.MULTILINE)
    export_row = re.search(r"^\|\s*`/api/language-audit/export`\s*\|.*$", source, re.MULTILINE)
    assert audit_row is not None
    assert export_row is not None
    assert "`KEEP_FOR_OFFICIAL_IDE`" in audit_row.group(0)
    assert "`KEEP_FOR_OFFICIAL_IDE_OR_BACKEND_ONLY`" in export_row.group(0)


def test_docs_and_changelog_exist() -> None:
    for path in [PLACEMENT_DOC, MIGRATION_DOC, CHANGELOG]:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip()
    assert "Phase 4.5-C2-D" in _read(MIGRATION_DOC)
    assert "All `MIGRATE_REQUIRED` legacy UI features have been migrated." in _read(CHANGELOG)
