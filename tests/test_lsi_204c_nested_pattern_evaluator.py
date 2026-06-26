from frontend.language_surface import (
    PatternEvaluator,
    RuntimeEnumValue,
    RuntimeStructValue,
    parse,
    pattern_match_result_from_json,
    pattern_match_result_to_json,
    resolve_struct_pattern,
)
from frontend.language_surface.nodes import MatchStatementNode, StructPatternNode


def _module_symbols(module):
    return {node.name: node for node in module.body if hasattr(node, "name")}


def _semantic_pattern(source: str):
    program = parse(source)
    for node in program.modules[0].body:
        for statement in getattr(node, "body", ()):
            if isinstance(statement, MatchStatementNode):
                pattern = statement.arms[0].pattern.pattern
                assert isinstance(pattern, StructPatternNode)
                return resolve_struct_pattern(pattern, _module_symbols(program.modules[0]))
    raise AssertionError("struct pattern not found")


def test_lsi_204c_nested_struct_pattern_matches_recursively():
    pattern = _semantic_pattern(
        """
        module Basic {
            enum Status {
                Active
                Inactive
            }

            struct Profile {
                status: Status
            }

            struct Person {
                profile: Profile
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { profile: Profile { status: Status.Active } } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    value = RuntimeStructValue.from_mapping(
        "Person",
        {
            "profile": RuntimeStructValue.from_mapping(
                "Profile",
                {"status": RuntimeEnumValue("Status", "Active")},
            )
        },
    )

    result = PatternEvaluator().evaluate(pattern, value)

    assert result.matched
    assert result.matched_fields == ("profile",)
    assert result.evaluation_trace == (
        "Person",
        "profile",
        "Profile",
        "status",
        "Status.Active",
        "Matched",
        "Matched",
        "Matched",
    )
    assert len(result.children) == 1
    profile_result = result.children[0]
    assert profile_result.matched
    assert profile_result.matched_fields == ("status",)
    assert profile_result.evaluation_trace == (
        "Profile",
        "status",
        "Status.Active",
        "Matched",
        "Matched",
    )
    assert profile_result.children[0].evaluation_trace == ("Status.Active", "Matched")


def test_lsi_204c_nested_child_failure_fails_parent_struct():
    pattern = _semantic_pattern(
        """
        module Basic {
            enum Status {
                Active
                Inactive
            }

            struct Profile {
                status: Status
            }

            struct Person {
                profile: Profile
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { profile: Profile { status: Status.Active } } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    value = RuntimeStructValue.from_mapping(
        "Person",
        {
            "profile": RuntimeStructValue.from_mapping(
                "Profile",
                {"status": RuntimeEnumValue("Status", "Inactive")},
            )
        },
    )

    result = PatternEvaluator().evaluate(pattern, value)

    assert not result.matched
    assert result.failed_field == "profile"
    assert result.failure_reason == "EnumVariantMismatch"
    assert result.children[0].failed_field == "status"
    assert result.evaluation_trace == (
        "Person",
        "profile",
        "Profile",
        "status",
        "Status.Inactive",
        "NotMatched",
    )


def test_lsi_204c_two_level_nested_struct_pattern_json_round_trips():
    pattern = _semantic_pattern(
        """
        module Basic {
            struct Detail {
                active: bool
            }

            struct Profile {
                detail: Detail
            }

            struct Person {
                profile: Profile
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { profile: Profile { detail: Detail { active: true } } } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    value = RuntimeStructValue.from_mapping(
        "Person",
        {
            "profile": RuntimeStructValue.from_mapping(
                "Profile",
                {
                    "detail": RuntimeStructValue.from_mapping(
                        "Detail",
                        {"active": True},
                    )
                },
            )
        },
    )

    result = PatternEvaluator().evaluate_pattern(pattern, value)
    encoded = pattern_match_result_to_json(result)

    assert encoded["children"][0]["children"][0]["children"][0] == {
        "node_type": "PatternMatchResult",
        "matched": True,
        "matched_fields": [],
        "failed_field": None,
        "failure_reason": None,
        "evaluation_trace": ["True", "Matched"],
        "children": [],
    }
    assert pattern_match_result_from_json(encoded) == result
