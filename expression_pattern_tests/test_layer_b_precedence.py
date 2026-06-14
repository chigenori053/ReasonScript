import unittest

from frontend.language_surface import (
    BinaryExpressionNode,
    BinaryOperator,
    ComparisonExpressionNode,
    LogicalExpressionNode,
    LogicalOperator,
    ParenthesizedExpressionNode,
    UnaryExpressionNode,
    parse_expression,
)


class LayerBPrecedenceTests(unittest.TestCase):
    def test_b_001_unary_binds_before_binary(self):
        root = parse_expression("-a * b").expression
        self.assertIsInstance(root, BinaryExpressionNode)
        self.assertIsInstance(root.left, UnaryExpressionNode)

    def test_b_002_multiply_before_add(self):
        root = parse_expression("1 + 2 * 3").expression
        self.assertEqual(root.operator, BinaryOperator.ADD)
        self.assertEqual(root.right.operator, BinaryOperator.MULTIPLY)

    def test_b_003_comparison_after_arithmetic(self):
        root = parse_expression("a + 1 >= b * 2").expression
        self.assertIsInstance(root, ComparisonExpressionNode)
        self.assertIsInstance(root.left, BinaryExpressionNode)
        self.assertIsInstance(root.right, BinaryExpressionNode)

    def test_b_004_logical_after_comparison_and_and_before_or(self):
        root = parse_expression("a > 1 || b < 2 && valid").expression
        self.assertIsInstance(root, LogicalExpressionNode)
        self.assertEqual(root.operator, LogicalOperator.OR)
        self.assertIsInstance(root.right, LogicalExpressionNode)
        self.assertEqual(root.right.operator, LogicalOperator.AND)

    def test_b_005_parentheses_override_and_are_preserved(self):
        root = parse_expression("(1 + 2) * 3").expression
        self.assertEqual(root.operator, BinaryOperator.MULTIPLY)
        self.assertIsInstance(root.left, ParenthesizedExpressionNode)


if __name__ == "__main__":
    unittest.main()
