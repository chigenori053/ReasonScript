from frontend.language_surface import (
    PatternEvaluator,
    PatternMatchResult,
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


def test_sp_e001_struct_pattern_matches_runtime_struct():
    pattern = _semantic_pattern(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            struct Person {
                role: Role
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: Role.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    value = RuntimeStructValue.from_mapping(
        "Person",
        {"role": RuntimeEnumValue("Role", "Admin")},
    )

    result = PatternEvaluator().evaluate(pattern, value)

    assert result == PatternMatchResult(
        True,
        ("role",),
        None,
        None,
        ("Person", "role", "Role.Admin", "Matched", "Matched"),
        (
            PatternMatchResult(
                True,
                (),
                None,
                None,
                ("Role.Admin", "Matched"),
            ),
        ),
    )


def test_sp_e002_struct_type_mismatch_fails():
    pattern = _semantic_pattern(
        """
        module Basic {
            struct Person {
                age: int
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { age: 10 } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    result = PatternEvaluator().evaluate(
        pattern,
        RuntimeStructValue.from_mapping("Animal", {"age": 10}),
    )

    assert not result.matched
    assert result.failure_reason == "StructTypeMismatch"


def test_sp_e003_missing_field_fails():
    pattern = _semantic_pattern(
        """
        module Basic {
            struct Person {
                age: int
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { age: 10 } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    result = PatternEvaluator().evaluate(pattern, RuntimeStructValue.from_mapping("Person", {}))

    assert not result.matched
    assert result.failed_field == "age"
    assert result.failure_reason == "MissingField"


def test_sp_e004_qualified_pattern_mismatch_fails():
    pattern = _semantic_pattern(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            struct Person {
                role: Role
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: Role.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    value = RuntimeStructValue.from_mapping(
        "Person",
        {"role": RuntimeEnumValue("Role", "User")},
    )

    result = PatternEvaluator().evaluate(pattern, value)

    assert not result.matched
    assert result.failed_field == "role"
    assert result.failure_reason == "EnumVariantMismatch"


def test_sp_e005_literal_and_wildcard_patterns():
    literal_pattern = _semantic_pattern(
        """
        module Basic {
            struct Person {
                age: int
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { age: 10 } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    wildcard_pattern = _semantic_pattern(
        """
        module Basic {
            struct Person {
                age: int
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { age: _ } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    value = RuntimeStructValue.from_mapping("Person", {"age": 10})

    assert PatternEvaluator().evaluate(literal_pattern, value).matched
    assert PatternEvaluator().evaluate(wildcard_pattern, value).matched


def test_sp_e006_default_pattern_inside_struct_field_not_matched():
    pattern = _semantic_pattern(
        """
        module Basic {
            struct Person {
                age: int
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { age: default } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    result = PatternEvaluator().evaluate(
        pattern,
        RuntimeStructValue.from_mapping("Person", {"age": 10}),
    )

    assert not result.matched
    assert result.failure_reason == "DefaultPatternNotAllowed"


def test_sp_e007_pattern_match_result_json_round_trip():
    result = PatternMatchResult(
        True,
        ("role",),
        None,
        None,
        ("Person", "role", "Role.Admin", "Matched"),
    )
    value = pattern_match_result_to_json(result)

    assert value == {
        "node_type": "PatternMatchResult",
        "matched": True,
        "matched_fields": ["role"],
        "failed_field": None,
        "failure_reason": None,
        "evaluation_trace": ["Person", "role", "Role.Admin", "Matched"],
        "children": [],
    }
    assert pattern_match_result_from_json(value) == result
