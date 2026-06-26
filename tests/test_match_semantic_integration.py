import json

import pytest

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import SurfaceSyntaxError, parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


def _pipeline(source: str):
    ir = compile_program(parse(source))[0]
    simulation = simulate(ir)
    return {
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": simulation,
        "knowledge": extract_knowledge(ir, simulation),
    }


SELECT_SOURCE = """
module Basic {
    fn Select(x: int) -> int {
        match x {
            1 => return 10
            2 => return 20
            3 => return 30
            default => return 0
        }
    }

    calculation Result {
        result = Select(ARG)
    }
}
"""


def test_msi_001_select_1_chooses_case_1():
    result = _pipeline(SELECT_SOURCE.replace("ARG", "1"))

    match_node = result["ir"]["metadata"]["function_ir"][0]["body"][0]
    assert match_node["node_type"] == "MatchExpressionIRNode"
    assert match_node["value"] == "x"
    assert match_node["cases"][0] == {
        "node_type": "MatchCaseIRNode",
        "pattern": 1,
        "target": "Select.match.1",
    }
    assert result["plan"]["selected_branch"] == "Select.match.1"
    assert result["plan"]["path_signature"] == "Select.match.1"


def test_msi_002_select_2_chooses_case_2():
    result = _pipeline(SELECT_SOURCE.replace("ARG", "2"))

    assert result["plan"]["selected_branch"] == "Select.match.2"
    assert result["simulation"]["selected_branch"] == "Select.match.2"
    match_event = next(
        item
        for item in result["simulation"]["trace"]
        if item.get("event_type") == "MatchEvaluation"
    )
    assert match_event["value"] == 2
    assert match_event["selected_case"] == 2
    assert match_event["selected_branch"] == "Select.match.2"


def test_msi_003_select_99_chooses_default():
    result = _pipeline(SELECT_SOURCE.replace("ARG", "99"))

    assert result["plan"]["selected_branch"] == "Select.match.default"
    assert result["simulation"]["selected_branch"] == "Select.match.default"


def test_msi_004_knowledge_preserves_match_evidence():
    result = _pipeline(SELECT_SOURCE.replace("ARG", "2"))

    unit = result["knowledge"]["knowledge"][0]
    assert unit["path_signature"] == "Select.match.2"
    assert unit["branch_id"] == "case_2"
    assert unit["evidence_path"] == ["Select.match.2"]
    assert unit["match_evidence"] == {"value": 2, "matched_case": 2}


def test_msi_005_duplicate_pattern_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="MSI-001"):
        _pipeline(
            """
            module Basic {
                fn Select(x: int) -> int {
                    match x {
                        1 => return 10
                        1 => return 20
                        default => return 0
                    }
                }

                calculation Result {
                    result = Select(1)
                }
            }
            """
        )


def test_msi_006_default_must_be_final():
    with pytest.raises(SurfaceSyntaxError, match="MSI-002"):
        _pipeline(
            """
            module Basic {
                fn Select(x: int) -> int {
                    match x {
                        default => return 0
                        1 => return 10
                    }
                }

                calculation Result {
                    result = Select(1)
                }
            }
            """
        )


def test_msi_007_repeat_match_execution_is_deterministic():
    first = _pipeline(SELECT_SOURCE.replace("ARG", "2"))
    second = _pipeline(SELECT_SOURCE.replace("ARG", "2"))
    first_knowledge = {k: v for k, v in first["knowledge"].items() if k != "generated_at"}
    second_knowledge = {k: v for k, v in second["knowledge"].items() if k != "generated_at"}

    assert first["plan"]["selected_branch"] == second["plan"]["selected_branch"]
    assert first["plan"]["path_signature"] == second["plan"]["path_signature"]
    assert json.dumps(first_knowledge, sort_keys=True, default=str) == json.dumps(
        second_knowledge,
        sort_keys=True,
        default=str,
    )
