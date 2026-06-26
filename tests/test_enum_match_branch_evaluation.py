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


SCORE_SOURCE = """
module Basic {
    enum Color {
        Red
        Blue
    }

    fn Score(color: Color) -> int {
        match color {
            Color.Red => return 1
            Color.Blue => return 2
        }
    }

    calculation Result {
        result = Score(ARG)
    }
}
"""


def test_emb_001_color_red_selects_red_branch():
    result = _pipeline(SCORE_SOURCE.replace("ARG", "Color.Red"))

    match_node = result["ir"]["metadata"]["function_ir"][0]["body"][0]
    assert match_node["cases"][0]["pattern"] == {
        "node_type": "EnumValuePatternNode",
        "enum_name": "Color",
        "value_name": "Red",
    }
    assert match_node["cases"][0]["target"] == "Score.match.Color.Red"
    assert result["plan"]["selected_branch"] == "Score.match.Color.Red"
    assert result["plan"]["path_signature"] == "Score.match.Color.Red"


def test_emb_002_color_blue_selects_blue_branch():
    result = _pipeline(SCORE_SOURCE.replace("ARG", "Color.Blue"))

    assert result["plan"]["selected_branch"] == "Score.match.Color.Blue"
    assert result["plan"]["path_signature"] == "Score.match.Color.Blue"
    assert result["simulation"]["selected_branch"] == "Score.match.Color.Blue"


def test_emb_003_knowledge_preserves_enum_match_evidence():
    result = _pipeline(SCORE_SOURCE.replace("ARG", "Color.Red"))

    unit = result["knowledge"]["knowledge"][0]
    assert unit["path_signature"] == "Score.match.Color.Red"
    assert unit["branch_id"] == "Color.Red"
    assert unit["evidence_path"] == ["Score.match.Color.Red"]
    assert unit["from_simulation"] is True
    assert unit["enum_match_evidence"] == {"enum": "Color", "variant": "Red"}


def test_emb_004_simulation_emits_enum_pattern_evaluation():
    result = _pipeline(SCORE_SOURCE.replace("ARG", "Color.Red"))

    event = next(
        item
        for item in result["simulation"]["trace"]
        if item.get("event_type") == "EnumPatternEvaluation"
    )
    assert event == {
        "step": 1,
        "state": "Score.match.Color.Red",
        "transition": "Score.match.Color.Red",
        "event": "match_evaluation",
        "event_type": "EnumPatternEvaluation",
        "enum_name": "Color",
        "input_variant": "Red",
        "pattern_variant": "Red",
        "result": True,
        "value": {"enum": "Color", "variant": "Red"},
        "selected_case": "Color.Red",
        "selected_branch": "Score.match.Color.Red",
    }


def test_emb_005_unmatched_enum_branch_does_not_survive_selected_path():
    result = _pipeline(SCORE_SOURCE.replace("ARG", "Color.Red"))

    selected_transition_ids = {
        step["transition_id"] for step in result["plan"]["selected_steps"]
    }
    assert "Score.match.Color.Red" in selected_transition_ids
    assert "Score.match.Color.Blue" not in selected_transition_ids
    assert result["plan"]["selected_branches"] == ["Score.match.Color.Red"]


def test_emb_006_repeated_enum_execution_is_deterministic():
    first = _pipeline(SCORE_SOURCE.replace("ARG", "Color.Red"))
    second = _pipeline(SCORE_SOURCE.replace("ARG", "Color.Red"))
    first_knowledge = {k: v for k, v in first["knowledge"].items() if k != "generated_at"}
    second_knowledge = {k: v for k, v in second["knowledge"].items() if k != "generated_at"}

    assert first["plan"]["selected_branch"] == second["plan"]["selected_branch"]
    assert first["plan"]["path_signature"] == second["plan"]["path_signature"]
    assert json.dumps(first_knowledge, sort_keys=True, default=str) == json.dumps(
        second_knowledge,
        sort_keys=True,
        default=str,
    )


def test_emb_007_unknown_enum_pattern_variant_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="ESR-001"):
        _pipeline(
            """
            module Basic {
                enum Color {
                    Red
                    Blue
                }

                fn Score(color: Color) -> int {
                    match color {
                        Color.Green => return 3
                        default => return 0
                    }
                }

                calculation Result {
                    result = Score(Color.Red)
                }
            }
            """
        )


def test_emb_008_enum_mismatch_pattern_does_not_match():
    result = _pipeline(
        """
        module Basic {
            enum Color {
                Red
                Blue
            }

            enum Traffic {
                Red
            }

            fn Score(color: Color) -> int {
                match color {
                    Traffic.Red => return 3
                    Color.Red => return 1
                    Color.Blue => return 2
                }
            }

            calculation Result {
                result = Score(Color.Red)
            }
        }
        """
    )

    assert result["plan"]["selected_branch"] == "Score.match.Color.Red"
