import json
from pathlib import Path

import pytest

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import SurfaceSyntaxError, parse
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


def test_opm_001_some_selects_some_branch():
    result = _pipeline("opm_001.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.some"
    assert result["plan"]["path_signature"] == "Score.match.some"
    assert "Score.match.some" in _function_return_ids(result)


def test_opm_002_none_selects_none_branch():
    result = _pipeline("opm_002.rsn")

    assert result["plan"]["selected_branch"] == "Score.match.none"
    assert result["plan"]["path_signature"] == "Score.match.none"
    assert result["simulation"]["selected_branch"] == "Score.match.none"


def test_opm_003_knowledge_records_some_evidence():
    result = _pipeline("opm_003.rsn")
    unit = result["knowledge"]["knowledge"][0]

    assert unit["path_signature"] == "Score.match.some"
    assert unit["branch_id"] == "some"
    assert unit["evidence_path"] == ["Score.match.some"]
    assert unit["optional_match_evidence"] == {"kind": "some"}


def test_opm_004_knowledge_records_none_evidence():
    result = _pipeline("opm_004.rsn")
    unit = result["knowledge"]["knowledge"][0]

    assert unit["path_signature"] == "Score.match.none"
    assert unit["branch_id"] == "none"
    assert unit["optional_match_evidence"] == {"kind": "none"}


def test_opm_005_simulation_emits_optional_evaluation_before_branch_selection():
    result = _pipeline("opm_005.rsn")
    trace = result["simulation"]["trace"]
    optional_index = next(
        index
        for index, event in enumerate(trace)
        if event.get("event_type") == "OptionalPatternEvaluation"
    )
    branch_index = next(
        index
        for index, event in enumerate(trace)
        if event.get("event_type") == "BranchSelection"
    )

    assert optional_index < branch_index
    assert trace[optional_index]["kind"] == "some"
    assert trace[optional_index]["result"] is True


def test_opm_006_repeated_execution_is_deterministic():
    first = _pipeline("opm_006.rsn")
    second = _pipeline("opm_006.rsn")
    first_knowledge = {k: v for k, v in first["knowledge"].items() if k != "generated_at"}
    second_knowledge = {k: v for k, v in second["knowledge"].items() if k != "generated_at"}

    assert first["plan"]["selected_branch"] == "Score.match.some|some"
    assert first["plan"]["path_signature"] == second["plan"]["path_signature"]
    assert first["simulation"]["path_signature"] == second["simulation"]["path_signature"]
    assert json.dumps(first_knowledge, sort_keys=True, default=str) == json.dumps(
        second_knowledge,
        sort_keys=True,
        default=str,
    )


def test_opm_function_ir_uses_dedicated_optional_pattern_nodes():
    result = _pipeline("opm_001.rsn")
    match_node = result["ir"]["metadata"]["function_ir"][0]["body"][0]
    selections = [
        node
        for node in result["ir"]["metadata"]["function_ir"][0]["body"]
        if node["node_type"] == "MatchSelectionIRNode"
    ]

    assert match_node["cases"][0]["pattern"] == {
        "node_type": "OptionalSomePatternNode",
        "binding": "x",
    }
    assert match_node["cases"][1]["pattern"] == {
        "node_type": "OptionalNonePatternNode",
    }
    assert selections[0]["canonical_path"] == ["some"]
    assert selections[1]["canonical_path"] == ["none"]


def test_opm_some_binding_is_available_only_in_selected_branch_context():
    result = _pipeline("opm_001.rsn")
    some_transition = next(
        transition
        for transition in result["ir"]["transitions"]
        if transition["transition_id"] == "Score.match.some"
    )
    none_transition = next(
        transition
        for transition in result["ir"]["transitions"]
        if transition["transition_id"] == "Score.match.none"
    )

    assert some_transition["effect"]["evaluation_context"]["x"] == 10
    assert some_transition["effect"]["return_value"] == 10
    assert "x" not in none_transition["effect"]["evaluation_context"]


def test_opm_optional_patterns_require_optional_match_value():
    with pytest.raises(SurfaceSyntaxError, match="OPM-002"):
        parse(
            """
            module Test {
                fn Score(value: int) -> int {
                    match value {
                        some(x) => return x
                        default => return 0
                    }
                }
            }
            """
        )

    with pytest.raises(SurfaceSyntaxError, match="OPM-003"):
        parse(
            """
            module Test {
                fn Score(value: int) -> int {
                    match value {
                        none => return 0
                        default => return 1
                    }
                }
            }
            """
        )
