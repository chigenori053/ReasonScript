from frontend.language_surface.expressions import parse_expression
from frontend.language_surface.nodes import ArrayTypeNode, PrimitiveKind, PrimitiveTypeNode
from frontend.language_surface.validation import _expression_type


def _type(source: str):
    return _expression_type(parse_expression(source).expression, {}, {})


def test_scalar_casts_have_explicit_semantic_types():
    assert _type("float(1)") == PrimitiveTypeNode(PrimitiveKind.FLOAT)
    assert _type("int(1.5)") == PrimitiveTypeNode(PrimitiveKind.INT)


def test_tensor_scalar_and_to_array_propagate_types():
    assert _type("tensor.scalar(t)") == PrimitiveTypeNode(PrimitiveKind.FLOAT)
    assert _type("tensor.to_array(t)") == ArrayTypeNode(PrimitiveTypeNode(PrimitiveKind.FLOAT))
