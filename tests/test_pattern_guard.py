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


def _guard_nodes(result):
    return [
        node
        for node in result["ir"]["metadata"]["function_ir"][0]["body"]
        if node.get("node_type") == "GuardExpressionIRNode"
    ]


def test_pg_001_struct_guard_selects_guarded_branch():
    result = _pipeline("pg_001.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Point.bindx|guard.x_gt_0"
    assert _guard_nodes(result)[0]["expression"] == "x > 0"
    assert result["simulation"]["path_signature"] == result["plan"]["path_signature"]


def test_pg_002_unknown_guard_identifier_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="PG-003"):
        parse((FIXTURE_DIR / "pg_002.rsn").read_text())


def test_pg_003_guard_must_be_bool():
    with pytest.raises(SurfaceSyntaxError, match="PG-001"):
        parse((FIXTURE_DIR / "pg_003.rsn").read_text())


def test_pg_004_false_guard_continues_to_next_branch():
    result = _pipeline("pg_004.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Point"
    assert result["simulation"]["selected_branch"] == "Score.match.Point"


def test_pg_guarded_struct_catch_all_does_not_satisfy_exhaustiveness():
    with pytest.raises(SurfaceSyntaxError, match="TV-8 NonExhaustiveStructMatch"):
        parse(
            """
            module Test {
                struct Point {
                    x: int
                }

                fn Score(point: Point) -> int {
                    match point {
                        Point { } when false => return 1
                    }
                }
            }
            """
        )


def test_pg_005_nested_struct_guard_uses_nested_bindings():
    result = _pipeline("pg_005.rsn")

    assert result["plan"]["selected_branch"] == (
        "Score.match.Person.position|Position.bindx_bindy|guard.x_gt_y"
    )
    guard_event = next(
        event
        for event in result["simulation"]["trace"]
        if event.get("event_type") == "GuardEvaluation"
    )
    assert guard_event["expression"] == "x > y"
    assert guard_event["result"] is True


def test_pg_006_optional_guard():
    result = _pipeline("pg_006.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.some|guard.x_gt_100"
    assert result["knowledge"]["knowledge"][0]["guard_evidence"] == {
        "expression": "x > 100",
        "result": True,
    }


def test_pg_007_enum_guard_with_fallback_same_pattern():
    result = _pipeline("pg_007.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Color.Red|guard.score_gt_80"
    guarded_transition = next(
        transition
        for transition in result["ir"]["transitions"]
        if transition["transition_id"] == result["plan"]["selected_branch"]
    )
    assert guarded_transition["effect"]["match_conditions"][0]["guard"][
        "node_type"
    ] == "GuardExpressionIRNode"


def test_pg_008_literal_guard_path_is_deterministic():
    first = _pipeline("pg_008.rsn")
    second = _pipeline("pg_008.rsn")

    assert first["plan"]["selected_branch"] == "Score.match.10|guard.flag"
    assert json.dumps(first["plan"], sort_keys=True) == json.dumps(
        second["plan"],
        sort_keys=True,
    )
    assert first["knowledge"]["knowledge"][0]["path_signature"] == (
        "Score.match.10|guard.flag"
    )
