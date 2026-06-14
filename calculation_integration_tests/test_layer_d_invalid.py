import unittest

from frontend.language_surface import SurfaceSyntaxError, parse


class LayerDInvalidCalculationTests(unittest.TestCase):
    def test_d_001_missing_result(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-010"):
            parse("module invalid {\ncalculation Risk {\nlet x = 1\n}\n}")

    def test_d_002_multiple_result(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-011"):
            parse(
                "module invalid {\ncalculation Risk {\n"
                "result = 1\nresult = 2\n}\n}"
            )

    def test_d_003_result_not_last(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-012"):
            parse(
                "module invalid {\ncalculation Risk {\n"
                "result = 1\nlet x = 2\n}\n}"
            )

    def test_d_004_invalid_statement(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-001"):
            parse(
                """
                module invalid {
                    constraint Adult
                    calculation Risk {
                        require Adult
                        result = 1
                    }
                }
                """
            )

    def test_d_005_invalid_goal_annotation(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-V008"):
            parse(
                """
                module invalid {
                    constraint RiskEvaluation
                    calculation Risk goal:RiskEvaluation {
                        result = 1
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
