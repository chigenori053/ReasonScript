import pytest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    CallExpressionNode,
    IdentifierNode,
    MemberAccessNode,
    ResultStatementNode,
    ReturnStatementNode,
    StructLiteralExpressionNode,
    expression_from_json,
    parse,
    parse_expression,
    to_json_value,
)
from frontend.language_surface.expressions import ExpressionSyntaxError


def test_ex_p001_empty_struct_literal():
    expression = parse_expression("Person {}").expression

    assert isinstance(expression, StructLiteralExpressionNode)
    assert expression.type_name == "Person"
    assert expression.fields == ()


def test_ex_p002_single_field():
    expression = parse_expression("Person { role: Role.Admin }").expression

    assert isinstance(expression, StructLiteralExpressionNode)
    assert len(expression.fields) == 1
    assert expression.fields[0].field_name == "role"


def test_ex_p003_multiple_fields_without_commas():
    expression = parse_expression("Person { role: Role.Admin status: Status.Active }").expression

    assert isinstance(expression, StructLiteralExpressionNode)
    assert [field.field_name for field in expression.fields] == ["role", "status"]


def test_ex_p004_qualified_expression_field():
    expression = parse_expression("Person { role: Role.Admin }").expression
    field_expression = expression.fields[0].expression.expression

    assert isinstance(field_expression, MemberAccessNode)
    assert isinstance(field_expression.object, IdentifierNode)
    assert field_expression.object.name == "Role"
    assert field_expression.member == "Admin"


def test_ex_p005_function_argument():
    expression = parse_expression("Check(Person { role: Role.Admin })").expression

    assert isinstance(expression, CallExpressionNode)
    assert isinstance(expression.arguments[0], StructLiteralExpressionNode)


def test_ex_i001_function_call_source_integration():
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

            fn Check(person: Person) -> int {
                return 1
            }

            fn Main() -> int {
                return Check(
                    Person {
                        role: Role.Admin
                    }
                )
            }
        }
        """
    )

    main = program.modules[0].body[3]
    result = main.body[0]
    assert isinstance(result, ReturnStatementNode)
    call = result.expression.expression
    assert isinstance(call, CallExpressionNode)
    assert isinstance(call.arguments[0], StructLiteralExpressionNode)


def test_ex_p006_calculation_expression():
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

            calculation Result {
                result = Person {
                    role: Role.Admin
                }
            }
        }
        """
    )

    calculation = program.modules[0].body[2]
    result = calculation.body[0]
    assert isinstance(result, ResultStatementNode)
    assert isinstance(result.expression.expression, StructLiteralExpressionNode)


def test_ex_a001_struct_literal_expression_node_json_shape():
    value = to_json_value(parse_expression("Person { role: Role.Admin }"))

    assert value["expression"]["node_type"] == "StructLiteralExpressionNode"
    assert value["expression"]["fields"][0]["field_name"] == "role"


def test_ex_a002_json_round_trip():
    expression = parse_expression("Person { role: Role.Admin }")
    value = to_json_value(expression)

    assert expression_from_json(value) == expression


def test_ex_a003_schema_validation():
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

            calculation Result {
                result = Person {
                    role: Role.Admin
                }
            }
        }
        """
    )

    SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
        to_json_value(program),
        "language_surface_ast.schema.json",
    )


def test_ex_201a_001_duplicate_fields():
    with pytest.raises(ExpressionSyntaxError, match="EX-201A-001"):
        parse_expression("Person { role: Role.Admin role: Role.User }")


def test_ex_201a_002_malformed_syntax():
    with pytest.raises(ExpressionSyntaxError, match="EX-201A-002"):
        parse_expression("Person { role: }")


def test_valid_struct_literal_argument_no_ex_v004():
    try:
        parse_expression("Check(Person { role: Role.Admin })")
    except ExpressionSyntaxError as error:
        pytest.fail(f"valid struct literal argument raised {error}")
