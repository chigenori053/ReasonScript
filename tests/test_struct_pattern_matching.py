from pathlib import Path

import pytest

from frontend.language_surface import (
    StructBindingPatternNode,
    StructPatternNode,
    compile_program,
)
from frontend.language_surface.parser import SurfaceSyntaxError, parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


FIXTURE_DIR = Path(__file__).parent


def _pipeline(name: str):
    ir = compile_program(parse((FIXTURE_DIR / name).read_text()))[0]
    simulation = simulate(ir)
    return {
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": simulation,
        "knowledge": extract_knowledge(ir, simulation),
    }


def _transition(result, transition_id: str):
    return next(
        transition
        for transition in result["ir"]["transitions"]
        if transition["transition_id"] == transition_id
    )


def test_spm_001_literal_field_match_selects_canonical_branch():
    result = _pipeline("spm_001.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Point.x0_y0"
    assert result["simulation"]["selected_branch"] == "Score.match.Point.x0_y0"


def test_spm_002_binding_extraction_is_branch_local():
    program = parse((FIXTURE_DIR / "spm_002.rsn").read_text())
    pattern = program.modules[0].body[1].body[0].arms[0].pattern.pattern
    assert isinstance(pattern, StructPatternNode)
    assert isinstance(pattern.fields[0].pattern, StructBindingPatternNode)

    result = _pipeline("spm_002.rsn")
    transition = _transition(result, "Score.match.Point.bindx_bindy")

    assert transition["effect"]["evaluation_context"]["x"] == 10
    assert transition["effect"]["evaluation_context"]["y"] == 20
    assert transition["effect"]["return_value"] == 30


def test_spm_003_mixed_literal_and_binding_pattern():
    result = _pipeline("spm_003.rsn")
    transition = _transition(result, "Score.match.Point.x0_bindy")

    assert result["plan"]["path_signature"] == "Score.match.Point.x0_bindy"
    assert transition["effect"]["evaluation_context"]["y"] == 20
    assert transition["effect"]["return_value"] == 20


def test_spm_004_unknown_field_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="SP-102"):
        parse((FIXTURE_DIR / "spm_004.rsn").read_text())


def test_spm_005_duplicate_field_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="SP-001"):
        parse((FIXTURE_DIR / "spm_005.rsn").read_text())


def test_spm_006_nested_struct_match_reuses_canonical_path():
    result = _pipeline("spm_006.rsn")

    assert result["plan"]["selected_branch"] == (
        "Score.match.Person.position|Position.x0_bindy"
    )
    assert result["simulation"]["path_signature"] == result["plan"]["path_signature"]


def test_spm_007_execution_plan_preserves_canonical_path():
    first = _pipeline("spm_007.rsn")
    second = _pipeline("spm_007.rsn")

    assert first["plan"]["selected_branch"] == "Score.match.Point.x0_bindy"
    assert first["plan"]["path_signature"] == second["plan"]["path_signature"]


def test_spm_008_knowledge_preserves_struct_match_evidence():
    result = _pipeline("spm_008.rsn")
    unit = result["knowledge"]["knowledge"][0]

    assert unit["path_signature"] == "Score.match.Point.bindx_bindy"
    assert unit["branch_id"] == "Point.bindx_bindy"
    assert unit["struct_match_evidence"] == {
        "struct": "Point",
        "matched_fields": ["x", "y"],
    }

    event_types = [event.get("event_type") for event in result["simulation"]["trace"]]
    assert event_types.index("StructPatternEvaluation") < event_types.index(
        "BranchSelection"
    )
