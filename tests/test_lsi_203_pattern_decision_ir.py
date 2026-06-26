from frontend.language_surface import (
    PatternDecisionBuilder,
    PatternDecisionIR,
    PatternMatchResult,
    pattern_decision_from_json,
    pattern_decision_to_json,
)
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


STRUCT_MATCH_SOURCE = """
module Basic {
    enum Role {
        Admin
        User
    }

    struct Person {
        role: Role
    }

    fn Check(person: Person) -> int {
        match person {
            Person { role: Role.Admin } => return 1
            default => return 0
        }
    }

    calculation Result {
        result = Check(Person { role: Role.Admin })
    }
}
"""


def test_lsi_203_builder_is_deterministic_and_json_round_trips():
    result = PatternMatchResult(
        True,
        ("role",),
        None,
        None,
        ("Person", "role", "Role.Admin", "Matched", "Matched"),
    )

    decision = PatternDecisionBuilder().build(
        result,
        matched_pattern="Person",
        branch_id="Person.Role.Admin",
    )
    assert decision == PatternDecisionIR(
        "StructPattern",
        True,
        "Person",
        ("role",),
        "Person.Role.Admin",
        ("Person", "role", "Role.Admin", "Matched", "Matched"),
        1.0,
        None,
    )

    encoded = pattern_decision_to_json(decision)
    assert encoded == {
        "node_type": "PatternDecisionIRNode",
        "pattern_kind": "StructPattern",
        "matched": True,
        "matched_pattern": "Person",
        "matched_fields": ["role"],
        "branch_id": "Person.Role.Admin",
        "evaluation_trace": ["Person", "role", "Role.Admin", "Matched", "Matched"],
        "confidence": 1.0,
    }
    assert pattern_decision_from_json(encoded) == decision


def test_lsi_203_reason_ir_contains_pattern_decision_ir_node():
    result = _pipeline(STRUCT_MATCH_SOURCE)

    transition = next(
        item
        for item in result["ir"]["transitions"]
        if item["transition_id"] == "Check.match.Person.Role.Admin"
    )
    decisions = transition["effect"]["pattern_decisions"]

    assert decisions == [
        {
            "node_type": "PatternDecisionIRNode",
            "pattern_kind": "StructPattern",
            "matched": True,
            "matched_pattern": "Person",
            "matched_fields": ["role"],
            "branch_id": "Person.Role.Admin",
            "evaluation_trace": ["Person", "role", "Role.Admin", "Matched", "Matched"],
            "confidence": 1.0,
        }
    ]


def test_lsi_203_planner_simulation_and_knowledge_consume_pattern_decision():
    result = _pipeline(STRUCT_MATCH_SOURCE)

    assert result["plan"]["selected_branch"] == "Check.match.Person.Role.Admin"
    assert result["plan"]["path_signature"] == "Check.match.Person.Role.Admin"
    assert result["simulation"]["selected_branch"] == "Check.match.Person.Role.Admin"

    pattern_event = next(
        item
        for item in result["simulation"]["trace"]
        if item.get("event_type") == "PatternDecision"
    )
    assert pattern_event["matched_pattern"] == "Person"
    assert pattern_event["matched_fields"] == ["role"]
    assert pattern_event["evaluation_trace"] == [
        "Person",
        "role",
        "Role.Admin",
        "Matched",
        "Matched",
    ]

    unit = result["knowledge"]["knowledge"][0]
    assert unit["branch_id"] == "Person.Role.Admin"
    assert unit["pattern"] == "StructPattern"
    assert unit["matched_pattern"] == "Person"
    assert unit["evaluation_trace"] == [
        "Person",
        "role",
        "Role.Admin",
        "Matched",
        "Matched",
    ]
