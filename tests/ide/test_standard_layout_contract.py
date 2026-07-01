"""Phase 3.5 standard IDE layout contract tests."""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_TSX = REPO_ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "App.tsx"
STANDARD_VIEWS = (
    REPO_ROOT
    / "apps"
    / "reasonscript-ide"
    / "ui"
    / "src"
    / "views"
    / "StandardLayoutViews.tsx"
)


def _tab_ids(source: str, const_name: str) -> list[str]:
    match = re.search(rf"const {const_name} = \[(.*?)\n  \];", source, re.S)
    assert match, f"{const_name} definition not found"
    return re.findall(r'id: "([^"]+)"', match.group(1))


def test_right_inspector_has_phase_35_primary_tabs() -> None:
    source = APP_TSX.read_text()
    assert _tab_ids(source, "rightInspectorTabs") == [
        "overview",
        "plan",
        "simulation",
        "knowledge",
        "artifacts",
    ]


def test_bottom_tool_window_has_phase_35_primary_tabs() -> None:
    source = STANDARD_VIEWS.read_text()
    match = re.search(r"export function BottomToolWindow\(.*?const tabs = \[(.*?)\n  \];", source, re.S)
    assert match, "BottomToolWindow tabs definition not found"
    assert re.findall(r'id: "([^"]+)"', match.group(1)) == [
        "problems",
        "output",
        "logs",
        "tests",
    ]


def test_old_raw_artifact_views_are_accessible_through_artifacts() -> None:
    source = STANDARD_VIEWS.read_text()
    for artifact_label in ["AST", "Semantic AST", "Reason IR", "Validation", "All Raw"]:
        assert f'label: "{artifact_label}"' in source


def test_diagnostics_and_output_are_not_primary_right_inspector_tabs() -> None:
    source = APP_TSX.read_text()
    ids = _tab_ids(source, "rightInspectorTabs")
    assert "diagnostics" not in ids
    assert "output" not in ids
    assert "runtime_ops" not in ids
