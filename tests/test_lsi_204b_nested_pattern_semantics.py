import pytest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    SemanticLiteralPattern,
    SemanticQualifiedPattern,
    SemanticStructPattern,
    SemanticWildcardPattern,
    SurfaceSyntaxError,
    parse,
    resolve_struct_pattern,
    semantic_pattern_from_json,
    semantic_pattern_to_json,
)
from frontend.language_surface.integration import compile_program
from frontend.language_surface.nodes import MatchStatementNode, StructPatternNode


def _module_symbols(module):
    return {node.name: node for node in module.body if hasattr(node, "name")}


def _first_struct_pattern(source: str):
    program = parse(source)
    for node in program.modules[0].body:
        for statement in getattr(node, "body", ()):
            if isinstance(statement, MatchStatementNode):
                pattern = statement.arms[0].pattern.pattern
                assert isinstance(pattern, StructPatternNode)
                return pattern, _module_symbols(program.modules[0])
    raise AssertionError("struct pattern not found")


def _semantic(source: str) -> SemanticStructPattern:
    pattern, symbols = _first_struct_pattern(source)
    return resolve_struct_pattern(pattern, symbols)


def test_sr_001_single_nested_pattern():
    semantic = _semantic(
        """
        module Basic {
            enum Status {
                Active
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

    profile = semantic.fields[0].pattern
    assert isinstance(profile, SemanticStructPattern)
    assert profile.struct_symbol == "Profile"
    assert isinstance(profile.fields[0].pattern, SemanticQualifiedPattern)


def test_sr_002_two_level_nested_pattern():
    semantic = _semantic(
        """
        module Basic {
            struct State {
                active: bool
            }

            struct Profile {
                state: State
            }

            struct Person {
                profile: Profile
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { profile: Profile { state: State { active: true } } } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    profile = semantic.fields[0].pattern
    state = profile.fields[0].pattern
    assert isinstance(state, SemanticStructPattern)
    assert state.struct_symbol == "State"


def test_sr_003_three_level_nested_pattern():
    semantic = _semantic(
        """
        module Basic {
            struct Detail {
                active: bool
            }

            struct State {
                detail: Detail
            }

            struct Profile {
                state: State
            }

            struct Person {
                profile: Profile
            }

            fn Score(person: Person) -> int {
                match person {
                    Person {
                        profile: Profile {
                            state: State {
                                detail: Detail {
                                    active: true
                                }
                            }
                        }
                    } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    profile = semantic.fields[0].pattern
    state = profile.fields[0].pattern
    detail = state.fields[0].pattern
    assert isinstance(detail, SemanticStructPattern)
    assert isinstance(detail.fields[0].pattern, SemanticLiteralPattern)


def test_sr_004_nested_wildcard():
    semantic = _semantic(
        """
        module Basic {
            struct Profile {
                age: int
            }

            struct Person {
                profile: Profile
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { profile: Profile { age: _ } } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    profile = semantic.fields[0].pattern
    assert isinstance(profile.fields[0].pattern, SemanticWildcardPattern)


def test_sr_005_nested_literal():
    semantic = _semantic(
        """
        module Basic {
            struct Profile {
                age: int
            }

            struct Person {
                profile: Profile
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { profile: Profile { age: 42 } } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    profile = semantic.fields[0].pattern
    literal = profile.fields[0].pattern
    assert isinstance(literal, SemanticLiteralPattern)
    assert literal.value == 42
    assert literal.literal_type == "Int"


def test_sr_006_nested_qualified_pattern():
    semantic = _semantic(
        """
        module Basic {
            enum Status {
                Active
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

    profile = semantic.fields[0].pattern
    qualified = profile.fields[0].pattern
    assert isinstance(qualified, SemanticQualifiedPattern)
    assert qualified.namespace == "Status"
    assert qualified.identifier == "Active"


def test_sr_007_unknown_nested_field_reports_sp_102():
    with pytest.raises(SurfaceSyntaxError, match="SP-102"):
        parse(
            """
            module Basic {
                struct Profile {
                    age: int
                }

                struct Person {
                    profile: Profile
                }

                fn Score(person: Person) -> int {
                    match person {
                        Person { profile: Profile { missing: 42 } } => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_sr_008_nested_type_mismatch_reports_sp_104():
    with pytest.raises(SurfaceSyntaxError, match="SP-104"):
        parse(
            """
            module Basic {
                struct Profile {
                    age: int
                }

                struct Person {
                    profile: Profile
                }

                fn Score(person: Person) -> int {
                    match person {
                        Person { profile: Profile { age: true } } => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_sr_009_recursive_json_round_trip_and_schema():
    semantic = _semantic(
        """
        module Basic {
            enum Status {
                Active
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
    value = semantic_pattern_to_json(semantic)

    assert value["fields"][0]["pattern"] == {
        "node_type": "SemanticStructPattern",
        "struct_symbol": "Profile",
        "fields": [
            {
                "node_type": "SemanticStructFieldPattern",
                "field_symbol": "status",
                "field_type": "Status",
                "pattern": {
                    "node_type": "SemanticQualifiedPattern",
                    "namespace": "Status",
                    "identifier": "Active",
                },
            }
        ],
    }
    SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
        value,
        "semantic_pattern.schema.json",
    )
    assert semantic_pattern_from_json(value) == semantic


def test_sr_010_nested_pattern_emits_canonical_pattern_decision_ir():
    ir = compile_program(
        parse(
            """
            module Basic {
                enum Status {
                    Active
                }

                struct Profile {
                    status: Status
                }

                struct Person {
                    profile: Profile
                }

                fn Check(person: Person) -> int {
                    match person {
                        Person { profile: Profile { status: Status.Active } } => return 1
                        default => return 0
                    }
                }

                calculation Result {
                    result = Check(Person { profile: Profile { status: Status.Active } })
                }
            }
            """
        )
    )[0]

    nested_transition = next(
        item
        for item in ir["transitions"]
        if item["transition_id"] == "Check.match.Person.profile|Profile.Status.Active"
    )
    assert nested_transition["effect"]["pattern_decisions"][0]["branch_id"] == (
        "Person.profile|Profile.Status.Active"
    )
