"""Phase 4.5-C2-B runtime IO trace migration contract tests."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "runtimeObservability.ts"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
SIMULATION_VIEW = UI_SRC / "views" / "SimulationTraceView.tsx"
OUTPUT_VIEW = UI_SRC / "views" / "RuntimeOutputView.tsx"
INPUT_VIEW = UI_SRC / "views" / "InputStateView.tsx"
CALC_VIEW = UI_SRC / "views" / "CalculationTraceView.tsx"
TRACE_VIEW = UI_SRC / "views" / "RuntimeTraceView.tsx"
SUMMARY_VIEW = UI_SRC / "views" / "RuntimeObservabilitySummaryView.tsx"
MIGRATION_DOC = REPO_ROOT / "docs" / "development" / "runtime_io_trace_migration_phase_4_5_c2_b.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
