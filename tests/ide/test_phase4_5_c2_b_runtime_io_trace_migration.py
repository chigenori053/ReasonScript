"""Phase 4.5-C2-B runtime IO trace migration contract tests."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "runtimeObservability.ts"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
SIMULATION_VIEW = UI_SRC / "views" / "SimulationTraceView.tsx"
APP = UI_SRC / "App.tsx"
OUTPUT_VIEW = UI_SRC / "views" / "RuntimeOutputView.tsx"
INPUT_VIEW = UI_SRC / "views" / "InputStateView.tsx"
CALC_VIEW = UI_SRC / "views" / "CalculationTraceView.tsx"
TRACE_VIEW = UI_SRC / "views" / "RuntimeTraceView.tsx"
SUMMARY_VIEW = UI_SRC / "views" / "RuntimeObservabilitySummaryView.tsx"
BRIDGE = UI_SRC / "bridge.ts"
FEATURE_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_migration_decision.md"
PLACEMENT_DOC = REPO_ROOT / "docs" / "development" / "legacy_feature_official_ide_placement.md"
MIGRATION_DOC = REPO_ROOT / "docs" / "development" / "runtime_io_trace_migration_phase_4_5_c2_b.md"
CHANGELOG = REPO_ROOT / "docs" / "changelog" / "ide_phase_4_5_c2_b_runtime_io_trace_migration.md"

MIGRATED_FEATURES = [
    "Runtime IO output",
    "Input state",
    "Calculation panel",
    "Runtime trace",
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


def test_runtime_observability_view_model_file_exists() -> None:
    assert VIEW_MODEL.is_file()
    source = _read(VIEW_MODEL)
    assert "export type RuntimeDataStatus" in source
    assert "export interface RuntimeObservabilityViewModel" in source
    assert "buildRuntimeObservabilityViewModel" in source


def test_official_ide_includes_all_runtime_migration_surfaces() -> None:
    source = _read(OUTPUT_VIEW) + _read(INPUT_VIEW) + _read(CALC_VIEW) + _read(TRACE_VIEW) + _read(SUMMARY_VIEW)
    for feature in ["Runtime IO Output", "Input State", "Calculation Trace", "Runtime Trace"]:
        assert feature in source


def test_output_integration_includes_runtime_output_events() -> None:
    source = _read(STANDARD_LAYOUT) + _read(OUTPUT_VIEW)
    assert "RuntimeOutputView" in source
    assert "runtimeOutput.events" in source
    assert "Runtime IO Output" in source


def test_simulation_integration_includes_input_calculation_and_runtime_trace() -> None:
    source = _read(SIMULATION_VIEW)
    assert "InputStateView" in source
    assert "CalculationTraceView" in source
    assert "RuntimeTraceView" in source
    assert '"runtime"' in source
    assert '"input"' in source
    assert '"calculation"' in source


def test_simulation_trace_fallback_is_documented_and_implemented() -> None:
    source = _read(VIEW_MODEL) + _read(TRACE_VIEW) + _read(MIGRATION_DOC)
    assert "simulation_trace" in source
    assert "fallback" in source
    assert "Runtime trace unavailable; showing simulation trace fallback." in source


def test_standard_layout_top_level_right_inspector_tabs_remain_unchanged() -> None:
    assert _app_right_inspector_ids() == ["overview", "plan", "simulation", "knowledge", "artifacts"]


def test_no_new_legacy_endpoint_dependency_is_introduced() -> None:
    source = _read(BRIDGE) + _read(VIEW_MODEL) + _read(STANDARD_LAYOUT) + _read(APP)
    assert 'fetch("/api/analyze"' in source
    # Later C2 phases intentionally add /api/export, /api/import, /api/diff,
    # /api/language-audit, and /api/examples for explicit migrated operations.
    # C2-B still must not depend on the other legacy-only workflow endpoints.
    for endpoint in LEGACY_ENDPOINTS:
        if endpoint == "/api/examples":
            continue
        assert endpoint not in source


def test_missing_runtime_data_has_fallback_empty_states() -> None:
    source = _read(OUTPUT_VIEW) + _read(INPUT_VIEW) + _read(CALC_VIEW) + _read(TRACE_VIEW)
    for text in [
        "No runtime output reported.",
        "No input state reported.",
        "No calculation details reported.",
        "No runtime trace reported.",
        "Runtime trace unavailable; showing simulation trace fallback.",
        "Runtime trace unavailable.",
    ]:
        assert text in source


def test_legacy_feature_decision_docs_updated_to_migrated() -> None:
    source = _read(FEATURE_DOC)
    for feature in MIGRATED_FEATURES:
        row = re.search(rf"^\|\s*{re.escape(feature)}\s*\|.*$", source, re.MULTILINE)
        assert row is not None, feature
        assert "`MIGRATED`" in row.group(0)
    assert "ALL LEGACY FEATURE DECISIONS RESOLVED - READY FOR PHYSICAL REMOVAL PLANNING" in source


def test_docs_and_changelog_exist() -> None:
    for path in [PLACEMENT_DOC, MIGRATION_DOC, CHANGELOG]:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip()
    assert "Phase 4.5-C2-B" in _read(MIGRATION_DOC)
    assert "Runtime migrated" in _read(CHANGELOG)
