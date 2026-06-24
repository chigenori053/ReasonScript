import json

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import parse
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
    fn Select(flag: bool) -> int {
        if flag {
            return 1
        }

        return 0
    }

    calculation Result {
        result = Select(ARG)
    }
}
"""


def test_cbe_001_select_true_chooses_true_branch():
    result = _pipeline(SELECT_SOURCE.replace("ARG", "true"))

    branch = result["ir"]["metadata"]["function_ir"][0]["body"][0]
    assert branch["node_type"] == "ConditionalBranchIRNode"
    assert branch["condition_type"] == "Bool"
    assert result["plan"]["selected_branch"] == "Select.return.true"
    assert result["plan"]["selected_branches"] == ["Select.return.true"]
    assert result["plan"]["path_signature"] == "Select.return.true"


def test_cbe_002_select_false_chooses_false_branch():
    result = _pipeline(SELECT_SOURCE.replace("ARG", "false"))

    assert result["plan"]["selected_branch"] == "Select.return.false"
    assert result["plan"]["selected_branches"] == ["Select.return.false"]
    assert result["plan"]["path_signature"] == "Select.return.false"


def test_cbe_003_knowledge_preserves_false_branch_evidence():
    result = _pipeline(SELECT_SOURCE.replace("ARG", "false"))

    unit = result["knowledge"]["knowledge"][0]
    assert unit["target"] == "Result.state.result"
    assert unit["branch_id"] == "false"
    assert unit["path_signature"] == "Select.return.false"
    assert unit["evidence_path"] == ["Select.return.false"]


def test_cbe_004_nested_branch_evaluation_uses_argument_context():
    result = _pipeline(
        """
        module Basic {
            fn Score(a: bool, b: bool) -> int {
                if a {
                    if b {
                        return 3
                    }

                    return 2
                }

                return 1
            }

            calculation Result {
                result = Score(true, false)
            }
        }
        """
    )

    assert result["plan"]["selected_branch"] == "Score.return.a_true_b_false"
    assert result["plan"]["path_signature"] == "Score.return.a_true_b_false"
    assert result["simulation"]["selected_branch"] == "Score.return.a_true_b_false"
    event = next(
        item
        for item in result["simulation"]["trace"]
        if item.get("event_type") == "BranchSelection"
    )
    assert event["conditions"] == [
        {"condition": "a", "value": True},
        {"condition": "b", "value": False},
    ]


def test_cbe_005_repeat_execution_is_deterministic():
    first = _pipeline(SELECT_SOURCE.replace("ARG", "false"))
    second = _pipeline(SELECT_SOURCE.replace("ARG", "false"))
    first_knowledge = {k: v for k, v in first["knowledge"].items() if k != "generated_at"}
    second_knowledge = {k: v for k, v in second["knowledge"].items() if k != "generated_at"}

    assert first["plan"]["selected_branch"] == second["plan"]["selected_branch"]
    assert first["plan"]["path_signature"] == second["plan"]["path_signature"]
    assert json.dumps(first_knowledge, sort_keys=True, default=str) == json.dumps(
        second_knowledge,
        sort_keys=True,
        default=str,
    )
