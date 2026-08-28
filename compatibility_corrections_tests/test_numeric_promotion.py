from frontend.language_surface.expressions import parse_expression
from frontend.language_surface.nodes import PrimitiveKind, PrimitiveTypeNode
from frontend.language_surface.validation import _expression_type


def _type(source: str):
    return _expression_type(parse_expression(source).expression, {}, {})


def test_mixed_numeric_arithmetic_promotes_to_float():
    expected = PrimitiveTypeNode(PrimitiveKind.FLOAT)
    assert _type("1 + 2.0") == expected
    assert _type("1.0 * 2") == expected


def test_integer_division_has_float_semantics():
    assert _type("4 / 2") == PrimitiveTypeNode(PrimitiveKind.FLOAT)
