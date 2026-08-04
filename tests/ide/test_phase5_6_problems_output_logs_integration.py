"""Phase 5.6 Problems / Output / Logs final integration contract tests."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SRC = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src"
VIEW_MODEL = UI_SRC / "viewModels" / "problemsOutputLogsIntegration.ts"
STANDARD_LAYOUT = UI_SRC / "views" / "StandardLayoutViews.tsx"
APP = UI_SRC / "App.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_merge_and_grouping_helpers_exist() -> None:
    source = _read(VIEW_MODEL)
    assert "mergeProblemsSources" in source
    assert "buildLogsGroups" in source
    assert "export type LogsGroupKey" in source
    for group in ["backend", "analyzer", "runtime", "ide"]:
        assert f'"{group}"' in source


def test_problems_supports_current_workspace_all_filter() -> None:
    source = _read(STANDARD_LAYOUT)
    assert "problemsScope" in source
    assert '"current"' in source
    assert '"workspace"' in source
    assert '"all"' in source


def test_output_groups_operation_logs() -> None:
    source = _read(STANDARD_LAYOUT)
    assert "Workspace / Project Validation Logs" in source


def test_logs_separate_backend_analyzer_runtime_ide() -> None:
    source = _read(STANDARD_LAYOUT)
    assert "buildLogsGroups" in source
    assert "logsGroups" in source


def test_existing_migrated_feature_outputs_still_present() -> None:
    source = _read(STANDARD_LAYOUT)
    for view in [
        "DiagnosticsView",
        "DiagnosticsAnalysisView",
        "RuntimeOutputView",
        "ArtifactOperationLogsView",
        "LanguageAuditLogsView",
        "SampleOperationLogsView",
        "RuntimeOperationsView",
    ]:
        assert view in source


def test_app_deduplicates_problems_via_merge_helper() -> None:
    source = _read(APP)
    assert "mergeProblemsSources" in source
