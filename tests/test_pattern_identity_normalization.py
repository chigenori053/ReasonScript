import json
from pathlib import Path

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import parse
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


def _selected_transition(result):
    selected = result["plan"]["selected_branch"]
    return next(
        transition
        for transition in result["ir"]["transitions"]
        if transition["transition_id"] == selected
    )


def _selected_match_condition(result):
    transition = _selected_transition(result)
    return transition["effect"]["match_conditions"][-1]


def _selected_knowledge_unit(result):
    return result["knowledge"]["knowledge"][0]


def _assert_identity(result, pattern_id: str, pattern_type: str):
    expected = {
        "pattern_id": pattern_id,
        "pattern_type": pattern_type,
        "canonical_path": pattern_id,
    }

    assert result["plan"]["pattern_identity"] == expected
    assert result["simulation"]["pattern_identity"] == expected
    assert _selected_knowledge_unit(result)["pattern_identity"] == expected
    assert _selected_match_condition(result)["pattern_identity"] == expected
    assert result["plan"]["path_signature"] == expected["canonical_path"]

    branch_event = next(
        event
        for event in result["simulation"]["trace"]
        if event.get("event_type") == "BranchSelection"
    )
    assert branch_event["pattern_identity"] == expected


def _selection_identities(result):
    return [
        node["pattern_identity"]
        for node in result["ir"]["metadata"]["function_ir"][0]["body"]
        if node.get("node_type") == "MatchSelectionIRNode"
    ]


def test_pin_001_enum_pattern_identity():
    result = _pipeline("pin_001.rsn")

    _assert_identity(result, "Score.match.Color.Blue", "Enum")
    assert {
        identity["pattern_id"]
        for identity in _selection_identities(result)
    } == {"Score.match.Color.Red", "Score.match.Color.Blue"}


def test_pin_002_struct_pattern_identity():
    result = _pipeline("pin_002.rsn")

    _assert_identity(result, "Score.match.Point.x0_bindy", "Struct")


def test_pin_003_optional_pattern_identity():
    result = _pipeline("pin_003.rsn")

    _assert_identity(result, "Score.match.some", "Optional")


def test_pin_004_nested_pattern_identity():
    result = _pipeline("pin_004.rsn")

    _assert_identity(result, "Score.match.Color.Red|Shape.Circle", "NestedStruct")


def test_pin_005_guard_pattern_identity():
    result = _pipeline("pin_005.rsn")

    _assert_identity(result, "Score.match.Point.bindx|guard.x_gt_0", "Guard")


def test_pin_006_or_pattern_identity_uses_selected_alternative_only():
    result = _pipeline("pin_006.rsn")

    _assert_identity(result, "Score.match.Color.Blue", "Enum")
    assert result["plan"]["selected_pattern"] == "Color.Blue"
    assert result["plan"]["pattern_identity"]["pattern_id"] == result["plan"]["selected_branch"]
    assert "Color.Red|Color.Blue" not in json.dumps(result["plan"], sort_keys=True)


def test_pin_007_repeated_compilation_produces_identical_pattern_identity():
    first = _pipeline("pin_007.rsn")
    second = _pipeline("pin_007.rsn")

    _assert_identity(first, "Score.match.Person.position|Position.x0_bindy", "NestedStruct")
    assert first["plan"]["pattern_identity"] == second["plan"]["pattern_identity"]
    assert first["simulation"]["pattern_identity"] == second["simulation"]["pattern_identity"]
    assert _selected_knowledge_unit(first)["pattern_identity"] == (
        _selected_knowledge_unit(second)["pattern_identity"]
    )
