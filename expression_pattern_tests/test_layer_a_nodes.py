import unittest

from frontend.language_surface import (
    BinaryExpressionNode,
    BooleanLiteralNode,
    CallExpressionNode,
    ComparisonExpressionNode,
    FloatLiteralNode,
    IdentifierNode,
    IntegerLiteralNode,
    LogicalExpressionNode,
    MemberAccessNode,
    NullLiteralNode,
    StringLiteralNode,
    UnaryExpressionNode,
    parse_expression,
)


class LayerAExpressionNodeTests(unittest.TestCase):
    def test_a_001_through_a_005_literals_and_identifier(self):
        cases = {
            "42": (IntegerLiteralNode, 42),
            "3.14": (FloatLiteralNode, 3.14),
            "true": (BooleanLiteralNode, True),
            '"hello"': (StringLiteralNode, "hello"),
            "null": (NullLiteralNode, None),
            "score": (IdentifierNode, "score"),
        }
        for source, (node_type, expected) in cases.items():
            with self.subTest(source=source):
                node = parse_expression(source).expression
                self.assertIsInstance(node, node_type)
                if expected is not None:
                    self.assertEqual(
                        getattr(node, "value", getattr(node, "name", None)), expected
                    )

    def test_a_006_through_a_011_composite_expression_nodes(self):
        cases = {
            "-score": UnaryExpressionNode,
            "a + b": BinaryExpressionNode,
            "score > 80": ComparisonExpressionNode,
            "adult && verified": LogicalExpressionNode,
            "user.profile.age": MemberAccessNode,
            "risk(score, age)": CallExpressionNode,
        }
        for source, node_type in cases.items():
            with self.subTest(source=source):
                self.assertIsInstance(parse_expression(source).expression, node_type)


if __name__ == "__main__":
    unittest.main()
