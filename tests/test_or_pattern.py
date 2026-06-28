import json
from pathlib import Path

import pytest

from frontend.language_surface.integration import compile_program
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


def test_op_001_enum_or_selects_matching_alternative():
    result = _pipeline("op_001.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Color.Blue"
    assert result["simulation"]["path_signature"] == "Score.match.Color.Blue"
    assert result["knowledge"]["knowledge"][0]["or_pattern_evidence"] == {
        "selected_alternative": 1,
        "selected_case": "Color.Blue",
        "alternative_count": 2,
    }


def test_op_002_literal_or_selects_matching_alternative():
    result = _pipeline("op_002.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.2"
    alternative_events = [
        event
        for event in result["simulation"]["trace"]
        if event.get("event_type") == "AlternativePatternEvaluation"
    ]
    assert [event["result"] for event in alternative_events] == [False, True]


def test_op_003_struct_or_selects_matching_alternative():
    result = _pipeline("op_003.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Point.y0"
    assert result["knowledge"]["knowledge"][0]["match_evidence"]["matched_case"] == "Point.y0"


def test_op_004_optional_or_supports_some_value_pattern():
    result = _pipeline("op_004.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.some.0"
    assert result["knowledge"]["knowledge"][0]["or_pattern_evidence"]["selected_alternative"] == 1


def test_op_005_duplicate_alternative_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="OP-004 DuplicateOrPattern"):
        parse((FIXTURE_DIR / "op_005.rsn").read_text())


def test_op_006_binding_environment_mismatch_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="OP-002 IncompatibleBindingEnvironment"):
        parse((FIXTURE_DIR / "op_006.rsn").read_text())


def test_op_007_guard_runs_after_selected_alternative():
    result = _pipeline("op_007.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Color.Blue|guard.score_gt_80"
    guard_event = next(
        event
        for event in result["simulation"]["trace"]
        if event.get("event_type") == "GuardEvaluation"
    )
    assert guard_event["result"] is True


def test_op_008_or_pattern_metadata_is_deterministic():
    first = _pipeline("op_008.rsn")
    second = _pipeline("op_008.rsn")

    assert json.dumps(first["ir"]["metadata"]["function_ir"], sort_keys=True) == json.dumps(
        second["ir"]["metadata"]["function_ir"],
        sort_keys=True,
    )
    assert json.dumps(first["knowledge"], sort_keys=True) == json.dumps(
        second["knowledge"],
        sort_keys=True,
    )
