"""Phase 4.5-C2-C export/import/diff migration contract tests."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "artifactWorkflow.ts"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"
BRIDGE = UI_SRC / "bridge.ts"
ARTIFACT_WORKFLOW_VIEW = UI_SRC / "views" / "ArtifactWorkflowView.tsx"
EXPORT_VIEW = UI_SRC / "views" / "ExportArtifactView.tsx"
IMPORT_VIEW = UI_SRC / "views" / "ImportArtifactView.tsx"
DIFF_VIEW = UI_SRC / "views" / "DiffArtifactView.tsx"
SUMMARY_VIEW = UI_SRC / "views" / "ArtifactWorkflowSummaryView.tsx"
LOGS_VIEW = UI_SRC / "views" / "ArtifactOperationLogsView.tsx"
FEATURE_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_migration_decision.md"
PLACEMENT_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_official_ide_placement.md"
MIGRATION_DOC = REPO_ROOT / "docs" / "development" / "export_import_diff_migration_phase_4_5_c2_c.md"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "ide_phase_4_5_c2_c_export_import_diff_migration.md"

MIGRATED_FEATURES = ["Export", "Import", "Diff"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _app_right_inspector_ids() -> list[str]:
    source = _read(APP)
    start = source.index("const rightInspectorTabs")
    end = source.index("  ];", start)
    return re.findall(r'id:\s*"([^"]+)"', source[start:end])


def test_artifact_workflow_view_model_file_exists() -> None:
    assert VIEW_MODEL.is_file()
    source = _read(VIEW_MODEL)
    for text in [
        "export type ArtifactOperationKind",
        "export type ArtifactOperationStatus",
        "export interface ArtifactWorkflowViewModel",
        "buildArtifactWorkflowViewModel",
        "artifactWorkflowIssuesAsPlatformDiagnostics",
    ]:
        assert text in source


def test_official_ide_includes_export_import_diff_surfaces() -> None:
    source = _read(ARTIFACT_WORKFLOW_VIEW) + _read(EXPORT_VIEW) + _read(IMPORT_VIEW) + _read(DIFF_VIEW)
    for text in [
        "Artifact Export",
        "Artifact Import",
        "Artifact Diff",
        "data-export-migration-surface",
        "data-import-migration-surface",
        "data-diff-migration-surface",
    ]:
        assert text in source


def test_artifacts_integration_includes_workflow_sections() -> None:
    source = _read(STANDARD_LAYOUT) + _read(ARTIFACT_WORKFLOW_VIEW)
    assert "ArtifactWorkflowView" in source
    assert 'id: "workflow"' in source
    assert "data-artifacts-export-import-diff" in source
    for callback in ["onExportArtifact", "onImportArtifact", "onSetArtifactDiffSlot", "onCompareArtifactDiff"]:
        assert callback in source


def test_overview_integration_includes_artifact_workflow_summary() -> None:
    source = _read(STANDARD_LAYOUT) + _read(SUMMARY_VIEW)
    assert "ArtifactWorkflowSummaryView" in source
    assert "Artifact Workflow Summary" in source
    assert "data-artifact-workflow-summary" in source
    for text in ["Export", "Import", "Diff", "Last operation"]:
        assert text in source


def test_problems_integration_includes_import_and_diff_issues() -> None:
    source = _read(APP) + _read(VIEW_MODEL)
    assert "artifactWorkflowIssuesAsPlatformDiagnostics" in source
    assert "artifactWorkflowDiagnostics" in source
    assert "importResult.validationIssues" in source
    assert "diffResult.issues" in source
    assert "Diff structural mismatch" in source


def test_output_integration_includes_artifact_operation_logs() -> None:
    source = _read(STANDARD_LAYOUT) + _read(LOGS_VIEW) + _read(APP)
    assert "ArtifactOperationLogsView" in source
    assert "Artifact Operation Logs" in source
    for text in ["Export started.", "Import started", "Diff started.", "No artifact workflow logs."]:
        assert text in source


def test_import_safety_policy_is_documented_and_implemented() -> None:
    source = _read(IMPORT_VIEW) + _read(MIGRATION_DOC) + _read(APP)
    assert "Validation-first import" in source
    assert "Failed import does not mutate" in source
    assert "failed import does not mutate `selectedfile.content`" in source.lower()
    assert "setSource" not in source[source.index("const handleImportArtifact") : source.index("const handleSetArtifactDiffSlot")]


def test_standard_layout_top_level_right_inspector_tabs_remain_unchanged() -> None:
    assert _app_right_inspector_ids() == ["overview", "plan", "simulation", "knowledge", "artifacts"]


def test_artifact_api_integration_exists_without_backend_contract_rewrite() -> None:
    source = _read(BRIDGE) + _read(APP)
    for endpoint in ['"/api/export"', '"/api/import"', '"/api/diff"']:
        assert endpoint in source
    assert "postArtifactOperation" in source
    assert "fetch(endpoint" in source
    assert "playground/backend/main.py" not in source


def test_missing_operation_state_has_fallback_empty_states() -> None:
    source = _read(EXPORT_VIEW) + _read(IMPORT_VIEW) + _read(DIFF_VIEW) + _read(ARTIFACT_WORKFLOW_VIEW) + _read(LOGS_VIEW)
    for text in [
        "No export has been run.",
        "No import has been run.",
        "No diff has been run.",
        "No artifact workflow issues.",
        "No artifact workflow logs.",
        "Export unavailable.",
        "Import unavailable.",
        "Diff unavailable.",
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


def test_docs_and_changelog_exist() -> None:
    for path in [PLACEMENT_DOC, MIGRATION_DOC, CHANGELOG]:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip()
    assert "Phase 4.5-C2-C" in _read(MIGRATION_DOC)
    assert "Artifact workflow migrated" in _read(CHANGELOG)
