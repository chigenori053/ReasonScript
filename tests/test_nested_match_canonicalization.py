import json
from pathlib import Path

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


FIXTURE_DIR = Path(__file__).parent


def _pipeline(name: str):
    source = (FIXTURE_DIR / name).read_text()
    ir = compile_program(parse(source))[0]
    simulation = simulate(ir)
    return {
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": simulation,
        "knowledge": extract_knowledge(ir, simulation),
    }


def _function_return_ids(result):
    return [
        transition["transition_id"]
        for transition in result["ir"]["transitions"]
        if transition["relation"] == "FunctionReturnTransition"
    ]


def test_nmc_001_nested_circle_path_is_canonical():
    result = _pipeline("nmc_001.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Color.Red|Shape.Circle"
    assert result["plan"]["selected_branches"] == ["Color.Red", "Shape.Circle"]
    assert "Score.match.Color.Red_and_match.Shape.Circle" not in _function_return_ids(result)


def test_nmc_002_nested_square_path_is_canonical():
    result = _pipeline("nmc_002.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Color.Red|Shape.Square"
    assert result["plan"]["selected_branches"] == ["Color.Red", "Shape.Square"]


def test_nmc_003_outer_blue_does_not_evaluate_nested_shape_path():
    result = _pipeline("nmc_003.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.Color.Blue"
    assert result["plan"]["selected_branches"] == ["Score.match.Color.Blue"]
    assert result["plan"]["path_signature"] == "Score.match.Color.Blue"


def test_nmc_004_plan_simulation_and_knowledge_share_path_signature():
    result = _pipeline("nmc_004.rsn")
    unit = result["knowledge"]["knowledge"][0]

    assert result["plan"]["selected_branch"] == result["plan"]["path_signature"]
    assert result["plan"]["path_signature"] == result["simulation"]["path_signature"]
    assert result["simulation"]["path_signature"] == unit["path_signature"]


def test_nmc_005_knowledge_branch_id_and_evidence_are_canonical():
    result = _pipeline("nmc_005.rsn")
    unit = result["knowledge"]["knowledge"][0]

    assert unit["branch_id"] == "Color.Red|Shape.Circle"
    assert unit["evidence_path"] == ["Color.Red", "Shape.Circle"]
    assert unit["enum_match_evidence"] == [
        {"enum": "Color", "variant": "Red"},
        {"enum": "Shape", "variant": "Circle"},
    ]
    assert "_and_match" not in json.dumps(unit, sort_keys=True)
    assert "PatternNode" not in unit["branch_id"]
    assert "EnumValuePatternNode" not in unit["branch_id"]


def test_nmc_006_repeated_compilation_produces_identical_canonical_paths():
    first = _pipeline("nmc_006.rsn")
    second = _pipeline("nmc_006.rsn")

    assert first["plan"]["path_signature"] == second["plan"]["path_signature"]
    assert first["simulation"]["path_signature"] == second["simulation"]["path_signature"]
    assert first["knowledge"]["knowledge"][0]["path_signature"] == (
        second["knowledge"]["knowledge"][0]["path_signature"]
    )


def test_nmc_function_ir_stores_canonical_path_components():
    result = _pipeline("nmc_001.rsn")
    selections = [
        node
        for node in result["ir"]["metadata"]["function_ir"][0]["body"]
        if node["node_type"] == "MatchSelectionIRNode"
    ]

    assert {
        tuple(selection["canonical_path"])
        for selection in selections
    } >= {
        ("Color.Red",),
        ("Color.Red", "Shape.Circle"),
        ("Color.Red", "Shape.Square"),
        ("Color.Blue",),
    }
