import unittest

from frontend.language_surface import (
    BinaryExpressionNode,
    ExpressionNode,
    ExpressionSyntaxError,
    IdentifierNode,
    LetNode,
    CalculationNode,
    ResultStatementNode,
    ModuleNode,
    ProgramNode,
    SurfaceValidationError,
    Visibility,
    parse_expression,
    parse_pattern,
    validate,
)


class LayerDInvalidSyntaxTests(unittest.TestCase):
    def test_d_001_missing_operand(self):
        for source in ("a +", "!"):
            with self.subTest(source=source), self.assertRaises(ExpressionSyntaxError):
                parse_expression(source)

    def test_d_002_invalid_operator(self):
        with self.assertRaises(ExpressionSyntaxError):
            parse_expression("a ** b")
        invalid = ProgramNode(
            (
                ModuleNode(
                    "invalid",
                    Visibility.PRIVATE,
                    (
                        CalculationNode(
                            "Invalid",
                            None,
                            (
                                LetNode(
                                    "x",
                                    ExpressionNode(
                                        BinaryExpressionNode(
                                            IdentifierNode("a"),
                                            "Power",
                                            IdentifierNode("b"),
                                        )
                                    ),
                                ),
                                ResultStatementNode(parse_expression("x")),
                            ),
                        ),
                    ),
                ),
            )
        )
        with self.assertRaisesRegex(SurfaceValidationError, "EX-V002"):
            validate(invalid)

    def test_d_003_unbalanced_parentheses(self):
        with self.assertRaisesRegex(ExpressionSyntaxError, "unbalanced"):
            parse_expression("(a + b")

    def test_d_004_invalid_member_access(self):
        for source in ("user.", "user.1"):
            with self.subTest(source=source), self.assertRaises(ExpressionSyntaxError):
                parse_expression(source)

    def test_d_005_invalid_call(self):
        for source in ("risk(,score)", "risk(score,)", "risk(score"):
            with self.subTest(source=source), self.assertRaises(ExpressionSyntaxError):
                parse_expression(source)

    def test_d_006_empty_pattern(self):
        with self.assertRaisesRegex(ExpressionSyntaxError, "PT-V001"):
            parse_pattern("")


if __name__ == "__main__":
    unittest.main()
