"""Phase 4.5-C2-A diagnostics and analysis migration contract tests."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "analysisDiagnostics.ts"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"
SUMMARY_VIEW = UI_SRC / "views" / "AnalysisSummaryView.tsx"
PROBLEMS_VIEW = UI_SRC / "views" / "DiagnosticsAnalysisView.tsx"
BRIDGE = UI_SRC / "bridge.ts"
FEATURE_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_migration_decision.md"
PLACEMENT_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_official_ide_placement.md"
MIGRATION_DOC = REPO_ROOT / "docs" / "development" / "diagnostics_analysis_migration_phase_4_5_c2_a.md"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "ide_phase_4_5_c2_a_diagnostics_analysis_migration.md"

MIGRATED_FEATURES = [
    "Strict diagnostics",
    "Cycle diagnostics",
    "Exhaustiveness",
    "Type coverage",
    "Ownership analysis",
    "Determinism",
    "Complexity",
]

LEGACY_ENDPOINTS = [
    "/api/validate",
    "/api/run-all",
    "/api/pipeline",
    "/api/baseline",
    "/api/examples",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _app_right_inspector_ids() -> list[str]:
    source = _read(APP)
    start = source.index("const rightInspectorTabs")
    end = source.index("  ];", start)
    return re.findall(r'id:\s*"([^"]+)"', source[start:end])


def test_analysis_diagnostics_view_model_file_exists() -> None:
    assert VIEW_MODEL.is_file()
    source = _read(VIEW_MODEL)
    assert "export type AnalysisStatus" in source
    assert "export interface DiagnosticsAnalysisViewModel" in source
    assert "buildDiagnosticsAnalysisViewModel" in source


def test_official_ide_includes_all_migration_surfaces() -> None:
    source = _read(VIEW_MODEL) + _read(SUMMARY_VIEW) + _read(PROBLEMS_VIEW)
    for feature in MIGRATED_FEATURES:
        assert feature in source


def test_problems_integration_includes_migrated_diagnostics() -> None:
    source = _read(STANDARD_LAYOUT) + _read(APP)
    assert "DiagnosticsAnalysisView" in source
    assert "diagnosticsAnalysisVm" in source
    assert "migratedAnalysisDiagnosticsAsPlatformDiagnostics" in source
    assert "Problems" in source


def test_overview_integration_includes_analysis_summary() -> None:
    source = _read(STANDARD_LAYOUT) + _read(SUMMARY_VIEW)
    assert "AnalysisSummaryView" in source
    assert "Overview Analysis Summary" in source
    for label in ["Strict", "Cycle", "Exhaustiveness", "Type Coverage", "Ownership", "Determinism", "Complexity"]:
        assert label in source


def test_standard_layout_top_level_right_inspector_tabs_remain_unchanged() -> None:
    assert _app_right_inspector_ids() == ["overview", "plan", "simulation", "knowledge", "artifacts"]


def test_no_new_legacy_endpoint_dependency_is_introduced() -> None:
    source = _read(BRIDGE) + _read(VIEW_MODEL) + _read(STANDARD_LAYOUT) + _read(APP)
    assert 'fetch("/api/analyze"' in source
    # Later C2 phases intentionally add /api/export, /api/import, /api/diff,
    # /api/language-audit, and /api/examples for explicit migrated operations.
    # C2-A still must not depend on the other legacy-only workflow endpoints.
    for endpoint in LEGACY_ENDPOINTS:
        if endpoint == "/api/examples":
            continue
        assert endpoint not in source


def test_missing_analysis_data_has_fallback_empty_states() -> None:
    source = _read(PROBLEMS_VIEW)
    for text in [
        "No strict diagnostics reported.",
        "No cycle diagnostics reported.",
        "No exhaustiveness data available.",
        "Type coverage unavailable.",
        "Ownership analysis unavailable.",
        "Determinism data unavailable.",
        "Complexity metrics unavailable.",
    ]:
        assert text in source


def test_legacy_feature_decision_docs_updated_to_migrated() -> None:
    source = _read(FEATURE_DOC)
    assert "`MIGRATED`" in source
    for feature in MIGRATED_FEATURES:
        row = re.search(rf"^\|\s*{re.escape(feature)}\s*\|.*$", source, re.MULTILINE)
        assert row is not None, feature
        assert "`MIGRATED`" in row.group(0)
    assert "ALL LEGACY FEATURE DECISIONS RESOLVED - READY FOR PHYSICAL REMOVAL PLANNING" in source


def test_docs_and_changelog_exist() -> None:
    for path in [PLACEMENT_DOC, MIGRATION_DOC, CHANGELOG]:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip()
    assert "Phase 4.5-C2-A" in _read(MIGRATION_DOC)
    assert "Partially migrated" in _read(CHANGELOG)
