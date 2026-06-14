import unittest

from calculation_semantics_tests.model import (
    MATHEMATICAL_TRANSITIONS,
    lower_program,
    parse_calculations,
    parse_expression,
)


class ExpressionLoweringTests(unittest.TestCase):
    def test_cs_02_equivalent_commutative_expressions_have_equal_graphs(self):
        self.assertEqual(
            parse_expression("width * height").canonical(),
            parse_expression("height * width").canonical(),
        )

    def test_cs_03_every_arithmetic_operator_creates_explicit_transition(self):
        expressions = {
            "x + y": "AddTransition",
            "x - y": "SubtractTransition",
            "x * y": "MultiplyTransition",
            "x / y": "DivideTransition",
            "x ^ y": "PowerTransition",
            "x % y": "ModuloTransition",
        }
        for source, expected in expressions.items():
            with self.subTest(source=source):
                self.assertEqual(parse_expression(source).kind, expected)

    def test_cs_04_mathematical_functions_map_to_transition_types(self):
        for function, expected in MATHEMATICAL_TRANSITIONS.items():
            with self.subTest(function=function):
                self.assertEqual(parse_expression(f"{function}(x)").kind, expected)

    def test_arithmetic_is_present_in_reason_ir(self):
        program = parse_calculations(
            """
            pub calculation Area goal:value {
                let width = 10
                let height = 20
                result = width * height
            }
            """
        )
        lowered = lower_program(program)
        self.assertEqual(
            lowered.reason_ir["transitions"][0]["relation"], "MultiplyTransition"
        )


if __name__ == "__main__":
    unittest.main()
