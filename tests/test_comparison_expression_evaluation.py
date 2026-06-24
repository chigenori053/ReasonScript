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


MAX_SOURCE = """
module Basic {
    fn Max(a: int, b: int) -> int {
        if a > b {
            return a
        }

        return b
    }

    calculation Result {
        result = Max(ARG_A, ARG_B)
    }
}
"""


EQUAL_SOURCE = """
module Basic {
    fn Equal(a: int, b: int) -> int {
        if a == b {
            return 1
        }

        return 0
    }

    calculation Result {
        result = Equal(ARG_A, ARG_B)
    }
}
"""


def test_cee_001_max_10_20_selects_false_branch():
    result = _pipeline(MAX_SOURCE.replace("ARG_A", "10").replace("ARG_B", "20"))

    branch = result["ir"]["metadata"]["function_ir"][0]["body"][0]
    assert branch["condition"]["expression"]["node_type"] == "ComparisonExpressionNode"
    transition = next(
        item
        for item in result["ir"]["transitions"]
        if item["transition_id"] == "Max.return.false"
    )
    comparison = transition["effect"]["branch_conditions"][0]["comparison"]
    assert comparison == {
        "node_type": "ComparisonExpressionIRNode",
        "operator": ">",
        "left": "a",
        "right": "b",
        "result_type": "Bool",
    }
    assert result["plan"]["selected_branch"] == "Max.return.false"
    assert result["plan"]["path_signature"] == "Max.return.false"


def test_cee_002_max_20_10_selects_true_branch():
    result = _pipeline(MAX_SOURCE.replace("ARG_A", "20").replace("ARG_B", "10"))

    assert result["plan"]["selected_branch"] == "Max.return.true"
    comparison_event = next(
        item
        for item in result["simulation"]["trace"]
        if item.get("event_type") == "ComparisonEvaluation"
    )
    assert comparison_event["expression"] == "a > b"
    assert comparison_event["left_value"] == 20
    assert comparison_event["right_value"] == 10
    assert comparison_event["result"] is True


def test_cee_003_equal_10_10_selects_true_branch():
    result = _pipeline(EQUAL_SOURCE.replace("ARG_A", "10").replace("ARG_B", "10"))

    assert result["plan"]["selected_branch"] == "Equal.return.true"


def test_cee_004_equal_10_20_selects_false_branch():
    result = _pipeline(EQUAL_SOURCE.replace("ARG_A", "10").replace("ARG_B", "20"))

    assert result["plan"]["selected_branch"] == "Equal.return.false"


def test_cee_005_nested_comparison_path_is_selected():
    result = _pipeline(
        """
        module Basic {
            fn Compare(a: int, b: int) -> int {
                if a > b {
                    if a > 100 {
                        return 3
                    }

                    return 2
                }

                return 1
            }

            calculation Result {
                result = Compare(120, 50)
            }
        }
        """
    )

    assert result["plan"]["selected_branch"] == "Compare.return.a_gt_b_and_a_gt_100"
    assert result["simulation"]["selected_branch"] == "Compare.return.a_gt_b_and_a_gt_100"
    unit = result["knowledge"]["knowledge"][0]
    assert unit["comparison_evidence"] == {
        "expression": "a > 100",
        "result": True,
    }


def test_cee_006_repeat_comparison_execution_is_deterministic():
    first = _pipeline(MAX_SOURCE.replace("ARG_A", "10").replace("ARG_B", "20"))
    second = _pipeline(MAX_SOURCE.replace("ARG_A", "10").replace("ARG_B", "20"))
    first_knowledge = {k: v for k, v in first["knowledge"].items() if k != "generated_at"}
    second_knowledge = {k: v for k, v in second["knowledge"].items() if k != "generated_at"}

    assert first["plan"]["selected_branch"] == second["plan"]["selected_branch"]
    assert first["plan"]["path_signature"] == second["plan"]["path_signature"]
    assert json.dumps(first_knowledge, sort_keys=True, default=str) == json.dumps(
        second_knowledge,
        sort_keys=True,
        default=str,
    )
