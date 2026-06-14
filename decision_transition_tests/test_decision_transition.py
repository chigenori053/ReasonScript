import unittest

from calculation_semantics_tests.model import (
    Assignment,
    Binding,
    Calculation,
    CalculationProgram,
    Decision,
    lower_program,
    parse_calculations,
    parse_expression,
)


class DecisionTransitionTests(unittest.TestCase):
    def test_cs_05_if_lowers_to_compare_and_decision_transitions(self):
        source = """
        pub calculation Maximum goal:value {
            let x = 10
            let y = 20
            if x > y {
                result = x
            } else {
                result = y
            }
        }
        """
        lowered = lower_program(parse_calculations(source))
        relations = [
            transition.relation for transition in lowered.calculations[0].transitions
        ]
        self.assertEqual(relations, ["CompareTransition", "DecisionTransition"])
        self.assertEqual(lowered, lower_program(parse_calculations(source)))

    def test_if_elseif_else_and_match_normalize_to_explicit_decisions(self):
        for kind in ("if", "elseif", "else", "match"):
            with self.subTest(kind=kind):
                calculation = Calculation(
                    f"Decision{kind}",
                    "value",
                    (
                        Binding(
                            f"Decision{kind}.binding.x",
                            "x",
                            parse_expression("1"),
                        ),
                        Decision(
                            parse_expression("x == 1"),
                            Assignment("result", parse_expression("x")),
                            Assignment("result", parse_expression("0")),
                            decision_kind=kind,
                        ),
                    ),
                )
                lowered = lower_program(CalculationProgram((calculation,)))
                self.assertEqual(
                    [item.relation for item in lowered.calculations[0].transitions],
                    ["CompareTransition", "DecisionTransition"],
                )


if __name__ == "__main__":
    unittest.main()
