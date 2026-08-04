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


def _range_event(result):
    return next(
        event
        for event in result["simulation"]["trace"]
        if event.get("event_type") == "RangeEvaluation"
    )


def _knowledge_unit(result):
    return result["knowledge"]["knowledge"][0]


def test_rp_001_inclusive_int_range_selects_branch():
    result = _pipeline("rp_001.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.range.80_100"
    assert result["plan"]["pattern_identity"] == {
        "pattern_id": "Score.match.range.80_100",
        "pattern_type": "Range",
        "canonical_path": "Score.match.range.80_100",
    }
    assert _range_event(result)["matched"] is True


def test_rp_002_half_open_range_excludes_upper_bound():
    result = _pipeline("rp_002.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.range.100_200"
    selections = [
        node
        for node in result["ir"]["metadata"]["function_ir"][0]["body"]
        if node.get("node_type") == "MatchSelectionIRNode"
    ]
    assert selections[0]["pattern"] == {
        "node_type": "RangePatternIRNode",
        "lower": 0,
        "upper": 100,
        "lower_inclusive": True,
        "upper_inclusive": False,
    }
    assert selections[0]["pattern_identity"]["pattern_id"] == "Score.match.range.0_lt_100"


def test_rp_003_float_range_selects_branch():
    result = _pipeline("rp_003.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.range.0_5_1_5"
    event = _range_event(result)
    assert event["value"] == 1.25
    assert event["lower"] == 0.5
    assert event["upper"] == 1.5


def test_rp_004_invalid_range_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="RP-003"):
        parse((FIXTURE_DIR / "rp_004.rsn").read_text())


def test_rp_005_range_guard_runs_after_range_evaluation():
    result = _pipeline("rp_005.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.range.80_100|guard.passed"
    trace = result["simulation"]["trace"]
    range_index = next(i for i, event in enumerate(trace) if event.get("event_type") == "RangeEvaluation")
    guard_index = next(i for i, event in enumerate(trace) if event.get("event_type") == "GuardEvaluation")
    assert range_index < guard_index
    assert result["plan"]["pattern_identity"]["pattern_type"] == "Guard"


def test_rp_006_or_range_uses_selected_alternative_only():
    result = _pipeline("rp_006.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.range.90_100"
    assert result["plan"]["selected_pattern"] == "range.90_100"
    assert result["plan"]["pattern_identity"]["pattern_id"] == "Score.match.range.90_100"
    alternative_events = [
        event
        for event in result["simulation"]["trace"]
        if event.get("event_type") == "AlternativePatternEvaluation"
    ]
    assert [event["matched"] for event in alternative_events] == [False, True]


def test_rp_007_pattern_identity_and_knowledge_range_evidence():
    result = _pipeline("rp_007.rsn")
    unit = _knowledge_unit(result)

    assert result["plan"]["pattern_identity"] == result["simulation"]["pattern_identity"]
    assert result["simulation"]["pattern_identity"] == unit["pattern_identity"]
    assert unit["range_evidence"] == {
        "value": 85,
        "lower": 80,
        "upper": 100,
        "lower_inclusive": True,
        "upper_inclusive": True,
        "matched": True,
    }


def test_rp_008_repeated_compilation_produces_identical_metadata():
    first = _pipeline("rp_008.rsn")
    second = _pipeline("rp_008.rsn")

    assert first["plan"]["selected_branch"] == "Score.match.range.50_lt_80"
    assert json.dumps(first["ir"]["metadata"]["function_ir"], sort_keys=True) == json.dumps(
        second["ir"]["metadata"]["function_ir"],
        sort_keys=True,
    )
    assert first["plan"]["pattern_identity"] == second["plan"]["pattern_identity"]
    assert _knowledge_unit(first)["range_evidence"] == _knowledge_unit(second)["range_evidence"]
