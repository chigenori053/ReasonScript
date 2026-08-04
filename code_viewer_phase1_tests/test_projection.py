from __future__ import annotations

from pathlib import Path

import pytest

from toolchain.code_viewer import Stage, project
from toolchain.code_viewer.projection import ProjectionError

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_SOURCE = ROOT / "examples" / "v0_5" / "003_calculation_dependency.rsn"

MULTI_MODULE_SOURCE = """module First {
  calculation Value {
    result = 1
  }
}

module Second {
  calculation Value {
    result = 2
  }
}
"""


def test_project_valid_source_all_stages_available():
    source = DEPENDENCY_SOURCE.read_text(encoding="utf-8")
    document = project(source, DEPENDENCY_SOURCE)

    assert document.ok is True
    assert document.module_names == ("CalculationDependency",)
    for stage in Stage:
        assert document.stages[stage].available, stage


def test_project_correlates_anchor_across_ir_and_plan_with_declaration_names():
    # This is the ground-truth relationship the whole Anchor design leans on
    # (design doc §6): effect.calculation and transition_id already carry the
    # declaration name, so no parser change is needed to correlate stages.
    source = DEPENDENCY_SOURCE.read_text(encoding="utf-8")
    document = project(source, DEPENDENCY_SOURCE)

    declared_symbols = {a.symbol for a in document.anchors if a.kind == "calculation"}
    ir_anchors = {node.anchor for node in document.stages[Stage.IR].nodes if node.anchor}
    plan_anchors = {node.anchor for node in document.stages[Stage.PLAN].nodes if node.anchor}

    assert declared_symbols == {"Base", "Answer"}
    assert ir_anchors == declared_symbols
    assert plan_anchors == declared_symbols


def test_project_degrades_gracefully_on_syntax_error():
    source = "module Broken {\n  calculation X {\n    result = \n  }\n}\n"
    document = project(source, Path("broken.rsn"))

    assert document.ok is False
    assert document.stages[Stage.SOURCE].available is True
    for stage in (Stage.SURFACE, Stage.SEMANTIC, Stage.IR, Stage.PLAN):
        view = document.stages[stage]
        assert view.available is False
        assert view.diagnostics
        assert view.diagnostics[0].code == "SyntaxError"


def test_project_source_stage_is_available_even_when_lexing_fails():
    # tokenize() raises on unsupported characters; the Source pane must still
    # render (design doc §9), just without highlighting.
    source = "module M {\n  calculation X {\n    result = `\n  }\n}\n"
    document = project(source, Path("unlexable.rsn"))

    assert document.stages[Stage.SOURCE].available is True
    assert document.tokens == ()
    assert document.source_lines[2] == "    result = `"


def test_project_selects_module_by_name():
    document_first = project(MULTI_MODULE_SOURCE, Path("multi.rsn"), module="First")
    document_second = project(MULTI_MODULE_SOURCE, Path("multi.rsn"), module="Second")

    assert document_first.active_module == "First"
    assert document_second.active_module == "Second"

    first_ir_anchors = {n.anchor for n in document_first.stages[Stage.IR].nodes if n.anchor}
    second_ir_anchors = {n.anchor for n in document_second.stages[Stage.IR].nodes if n.anchor}
    assert first_ir_anchors == {"Value"}
    assert second_ir_anchors == {"Value"}


def test_project_defaults_to_first_module_without_module_option():
    document = project(MULTI_MODULE_SOURCE, Path("multi.rsn"))
    assert document.active_module == "First"


def test_project_raises_for_unknown_module_name():
    with pytest.raises(ProjectionError) as excinfo:
        project(MULTI_MODULE_SOURCE, Path("multi.rsn"), module="DoesNotExist")
    assert excinfo.value.code == "CV-003"
