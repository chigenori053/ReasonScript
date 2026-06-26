import pytest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    QualifiedPatternNode,
    StructPatternNode,
    parse,
    parse_pattern,
    pattern_from_json,
    to_json_value,
)
from frontend.language_surface.expressions import ExpressionSyntaxError
from frontend.language_surface.parser import SurfaceSyntaxError


def test_sp_p001_empty_struct_pattern():
    pattern = parse_pattern("Person { }").pattern

    assert isinstance(pattern, StructPatternNode)
    assert pattern.type_name == "Person"
    assert pattern.fields == ()


def test_sp_p002_single_field():
    pattern = parse_pattern("Person { role: Admin }").pattern

    assert isinstance(pattern, StructPatternNode)
    assert len(pattern.fields) == 1
    assert pattern.fields[0].field_name == "role"


def test_sp_p003_multiple_fields():
    pattern = parse_pattern("Person { role: Role.Admin status: Status.Active }").pattern

    assert isinstance(pattern, StructPatternNode)
    assert [field.field_name for field in pattern.fields] == ["role", "status"]


def test_sp_p004_qualified_pattern_field():
    pattern = parse_pattern("Person { role: Role.Admin }").pattern

    assert isinstance(pattern, StructPatternNode)
    field_pattern = pattern.fields[0].pattern
    assert isinstance(field_pattern, QualifiedPatternNode)
    assert field_pattern.namespace == "Role"
    assert field_pattern.identifier == "Admin"


def test_sp_p005_duplicate_field():
    with pytest.raises(ExpressionSyntaxError, match="SP-001"):
        parse_pattern("Person { role: Role.Admin role: Role.User }")


def test_sp_p006_invalid_syntax():
    with pytest.raises(ExpressionSyntaxError, match="SP-002"):
        parse_pattern("Person { role: }")


def test_sp_a001_parser_generates_struct_pattern_node():
    program = parse(
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
                    Person {
                        role: Role.Admin
                    } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    function = program.modules[0].body[2]
    match_statement = function.body[0]
    pattern = match_statement.arms[0].pattern.pattern
    assert isinstance(pattern, StructPatternNode)
    assert pattern.type_name == "Person"
    assert pattern.fields[0].field_name == "role"


def test_sp_a002_json_round_trip():
    pattern = parse_pattern("Person { role: Role.Admin }")
    value = to_json_value(pattern)

    assert pattern_from_json(value) == pattern
    assert value["pattern"]["fields"][0]["pattern"] == {
        "node_type": "QualifiedPatternNode",
        "namespace": "Role",
        "identifier": "Admin",
    }


def test_sp_a003_schema_validation():
    program = parse(
        """
        module Basic {
            struct Person {
                role: int
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: 1 } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
        to_json_value(program), "language_surface_ast.schema.json"
    )


def test_valid_struct_pattern_no_longer_emits_pt_205():
    try:
        parse_pattern("Person { role: Role.Admin }")
    except ExpressionSyntaxError as error:
        pytest.fail(f"valid struct pattern raised {error}")


def test_duplicate_struct_field_from_source_is_sp_001():
    with pytest.raises(SurfaceSyntaxError, match="SP-001"):
        parse(
            """
            module Basic {
                struct Person {
                    role: int
                }

                fn Score(person: Person) -> int {
                    match person {
                        Person { role: 1 role: 2 } => return 1
                        default => return 0
                    }
                }
            }
            """
        )
