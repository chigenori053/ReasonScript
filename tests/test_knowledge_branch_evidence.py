import json

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import parse
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


def _pipeline(source: str):
    program = parse(source)
    ir = compile_program(program)[0]
    simulation = simulate(ir)
    return {
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": simulation,
        "knowledge": extract_knowledge(ir, simulation),
    }


def test_kbe_001_selected_branch_knowledge_keeps_evidence_path():
    result = _pipeline(
        """
        module Basic {
            fn Select(flag: bool) -> int {
                if flag {
                    return 1
                }

                return 0
            }

            calculation Result {
                result = Select(true)
            }
        }
        """
    )

    assert result["plan"]["selected_branch"] == "Select.return.true"
    assert result["simulation"]["selected_branch"] == "Select.return.true"
    assert any(
        item.get("event_type") == "BranchSelection"
        and item.get("branch") == "Select.return.true"
        for item in result["simulation"]["trace"]
    )
    assert result["knowledge"]["knowledge_count"] == 1
    unit = result["knowledge"]["knowledge"][0]
    assert unit["evidence_path"] == ["Select.return.true"]
    assert unit["path_signature"] == "Select.return.true"
    assert unit["branch_id"] == "true"


def test_kbe_002_all_branch_analysis_keeps_distinct_signatures():
    result = _pipeline(
        """
        module Basic {
            fn Select(flag: bool) -> int {
                if flag {
                    return 1
                }

                return 0
            }

            calculation Result {
                result = Select(true)
            }
        }
        """
    )

    knowledge = extract_knowledge(
        result["ir"],
        result["simulation"],
        include_all_branches=True,
    )
    signatures = {
        unit["path_signature"]
        for unit in knowledge["knowledge"]
        if unit["target"] == "Result.state.result"
    }
    assert knowledge["knowledge_count"] == 2
    assert signatures == {"Select.return.true", "Select.return.false"}


def test_kbe_003_path_signature_is_deterministic_after_export_import():
    result = _pipeline(
        """
        module Basic {
            fn Select(flag: bool) -> int {
                if flag {
                    return 1
                }

                return 0
            }

            calculation Result {
                result = Select(true)
            }
        }
        """
    )

    exported = json.loads(json.dumps(result["knowledge"], sort_keys=True))
    rerun = extract_knowledge(result["ir"], result["simulation"])
    assert exported["knowledge"][0]["path_signature"] == rerun["knowledge"][0]["path_signature"]
    assert exported["knowledge"][0]["evidence_path"] == rerun["knowledge"][0]["evidence_path"]


def test_kbe_004_identical_path_signatures_are_merged():
    ir = {
        "goal": {"target": "Result.state.result"},
        "initial_state": {"state_id": "Start"},
        "transitions": [
            {
                "transition_id": "Select.return.true",
                "source": "Start",
                "relation": "FunctionReturnTransition",
                "target": "Select.return.true",
            },
            {
                "transition_id": "Result.same.1",
                "source": "Select.return.true",
                "relation": "ResultTransition",
                "target": "Result.state.result",
            },
            {
                "transition_id": "Result.same.2",
                "source": "Select.return.true",
                "relation": "ResultTransition",
                "target": "Result.state.result",
            },
        ],
    }
    simulation = {"success": True, "selected_branch": "Select.return.true"}

    knowledge = extract_knowledge(ir, simulation)

    assert knowledge["knowledge_count"] == 1
    assert knowledge["knowledge"][0]["path_signature"] == "Select.return.true"
