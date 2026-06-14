import unittest

from frontend.language_surface import CalculationNode, Visibility, parse


class LayerADeclarationTests(unittest.TestCase):
    def test_a_001_basic_calculation(self):
        calculation = parse(
            """
            module finance {
                attribute income
                attribute factor
                calculation RiskScore {
                    result = income * factor
                }
            }
            """
        ).modules[0].body[-1]
        self.assertIsInstance(calculation, CalculationNode)
        self.assertEqual(calculation.visibility, Visibility.PRIVATE)

    def test_a_002_public_calculation(self):
        calculation = parse(
            """
            module finance {
                pub calculation RiskScore {
                    result = 1
                }
            }
            """
        ).modules[0].body[0]
        self.assertEqual(calculation.visibility, Visibility.PUBLIC)

    def test_a_003_goal_annotation(self):
        calculation = parse(
            """
            module finance {
                goal RiskEvaluation
                calculation RiskScore goal:RiskEvaluation {
                    result = 1
                }
            }
            """
        ).modules[0].body[-1]
        self.assertEqual(calculation.goal_annotation, "RiskEvaluation")


if __name__ == "__main__":
    unittest.main()
