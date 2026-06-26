import pytest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    IntegerLiteralNode,
    LiteralPatternNode,
    PatternNode,
    QualifiedPatternNode,
    StructFieldPatternNode,
    StructPatternNode,
    WildcardPatternNode,
    parse,
    parse_pattern,
    pattern_from_json,
    to_json_value,
)
from frontend.language_surface.expressions import (
    MAX_PATTERN_DEPTH,
    ExpressionSyntaxError,
)
from frontend.language_surface.parser import SurfaceSyntaxError
from frontend.language_surface.validation import SurfaceValidationError, _pattern


def test_np_a001_single_nested_pattern():
    pattern = parse_pattern(
        "Person { profile: Profile { status: Status.Active } }"
    ).pattern

    assert isinstance(pattern, StructPatternNode)
    profile = pattern.fields[0].pattern
    assert isinstance(profile, StructPatternNode)
    assert profile.type_name == "Profile"
    assert isinstance(profile.fields[0].pattern, QualifiedPatternNode)
    assert profile.fields[0].pattern.namespace == "Status"
    assert profile.fields[0].pattern.identifier == "Active"


def test_np_a002_two_level_nested_pattern_preserves_order():
    pattern = parse_pattern(
        """
        Person {
            profile: Profile {
                status: Status.Active
                tier: Tier.Gold
            }
            role: Role.Admin
        }
        """
    ).pattern

    assert isinstance(pattern, StructPatternNode)
    assert [field.field_name for field in pattern.fields] == ["profile", "role"]
    profile = pattern.fields[0].pattern
    assert isinstance(profile, StructPatternNode)
    assert [field.field_name for field in profile.fields] == ["status", "tier"]


def test_np_a003_three_level_nested_pattern():
    pattern = parse_pattern(
        """
        Person {
            profile: Profile {
                state: State {
                    active: true
                }
            }
        }
        """
    ).pattern

    profile = pattern.fields[0].pattern
    assert isinstance(profile, StructPatternNode)
    state = profile.fields[0].pattern
    assert isinstance(state, StructPatternNode)
    active = state.fields[0].pattern
    assert isinstance(active, LiteralPatternNode)
    assert active.value.value is True


def test_np_a004_wildcard_nested_pattern():
    pattern = parse_pattern("Person { profile: Profile { status: _ } }").pattern

    profile = pattern.fields[0].pattern
    assert isinstance(profile, StructPatternNode)
    assert isinstance(profile.fields[0].pattern, WildcardPatternNode)


def test_np_a005_literal_nested_pattern():
    pattern = parse_pattern("Person { profile: Profile { age: 42 } }").pattern

    profile = pattern.fields[0].pattern
    assert isinstance(profile, StructPatternNode)
    age = profile.fields[0].pattern
    assert isinstance(age, LiteralPatternNode)
    assert age.value.value == 42


def test_np_a006_invalid_nesting_reports_np_diagnostic():
    with pytest.raises(ExpressionSyntaxError, match="NP-002"):
        parse_pattern("Person { profile: Profile { status: } }")

    with pytest.raises(ExpressionSyntaxError, match="NP-003"):
        parse_pattern("Person { profile: Profile { status: Status.Active }")


def test_np_a007_recursive_struct_pattern_node_from_match_arm():
    program = parse(
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
                    Person {
                        profile: Profile {
                            status: Status.Active
                        }
                    } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    function = program.modules[0].body[3]
    match_statement = function.body[0]
    pattern = match_statement.arms[0].pattern.pattern
    assert isinstance(pattern, StructPatternNode)
    nested = pattern.fields[0].pattern
    assert isinstance(nested, StructPatternNode)
    assert nested.type_name == "Profile"


def test_np_a008_json_round_trip():
    pattern = parse_pattern(
        "Person { profile: Profile { status: Status.Active } }"
    )
    value = to_json_value(pattern)

    assert pattern_from_json(value) == pattern
    assert value["pattern"]["fields"][0]["pattern"] == {
        "node_type": "StructPatternNode",
        "type_name": "Profile",
        "fields": [
            {
                "node_type": "StructFieldPatternNode",
                "field_name": "status",
                "pattern": {
                    "node_type": "QualifiedPatternNode",
                    "namespace": "Status",
                    "identifier": "Active",
                },
            }
        ],
    }


def test_np_a009_schema_validation():
    program = parse(
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

    SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
        to_json_value(program), "language_surface_ast.schema.json"
    )


def test_np_a010_depth_limit_passes_for_shallow_nested_pattern():
    pattern = parse_pattern(_nested_pattern_source(8)).pattern

    assert isinstance(pattern, StructPatternNode)


def test_np_a011_depth_limit_exceeded_reports_np_010():
    with pytest.raises(ExpressionSyntaxError, match="NP-010 nested pattern depth exceeded"):
        parse_pattern(_nested_pattern_source(MAX_PATTERN_DEPTH + 2))


def test_np_a011_match_arm_collection_depth_limit_reports_np_010():
    nested_arm = "\n".join(
        f"                {line}"
        for line in _nested_pattern_lines(MAX_PATTERN_DEPTH + 2)
    )
    source = f"""
    module Basic {{
        fn Score(person: Person) -> int {{
            match person {{
{nested_arm}
                => return 1
                default => return 0
            }}
        }}
    }}
    """

    with pytest.raises(SurfaceSyntaxError, match="NP-010 nested pattern depth exceeded"):
        parse(source)


def test_np_a012_ast_validation_depth_guard_reports_np_010():
    pattern = _nested_pattern_node(MAX_PATTERN_DEPTH + 2)

    with pytest.raises(SurfaceValidationError, match="NP-010 nested pattern depth exceeded"):
        _pattern(pattern)


def _nested_pattern_source(depth: int) -> str:
    value = "1"
    for index in reversed(range(depth)):
        value = f"N{index} {{ f{index}: {value} }}"
    return value


def _nested_pattern_lines(depth: int) -> list[str]:
    if depth <= 0:
        return ["1"]
    lines = ["N0 {"]
    for index in range(1, depth):
        lines.append(f"f{index - 1}: N{index} {{")
    lines.append(f"f{depth - 1}: 1")
    lines.extend("}" for _ in range(depth))
    return lines


def _nested_pattern_node(depth: int) -> PatternNode:
    current = LiteralPatternNode(IntegerLiteralNode(1))
    for index in reversed(range(depth)):
        current = StructPatternNode(
            f"N{index}",
            (StructFieldPatternNode(f"f{index}", current),),
        )
    return PatternNode(current)
