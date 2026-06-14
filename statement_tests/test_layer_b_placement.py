import unittest

from frontend.language_surface import SurfaceSyntaxError, parse


class LayerBPlacementTests(unittest.TestCase):
    def assert_invalid(self, source, message="ST-V002"):
        with self.assertRaisesRegex(SurfaceSyntaxError, message):
            parse(source)

    def test_b_001_module_body_rejects_statements(self):
        self.assert_invalid("module invalid {\nlet x = 1\n}")

    def test_b_002_transition_body_accepts_only_transition_statements(self):
        parse(
            """
            module valid {
                constraint Ready
                goal Done
                transition Go {
                    Start -> Finish
                    require Ready
                    goal Done
                    reach Done
                    publish(order)
                }
            }
            """
        )
        self.assert_invalid(
            """
            module invalid {
                transition Go {
                    Start -> Finish
                    x = 1
                }
            }
            """
        )

    def test_b_003_calculation_body_accepts_calculation_statements(self):
        parse(
            """
            module valid {
                calculation Score {
                    let x = 1
                    x = x + 1
                    publish(x)
                    result = x
                }
            }
            """
        )

    def test_b_004_assignment_outside_calculation_is_invalid(self):
        self.assert_invalid(
            """
            module invalid {
                transition Go {
                    Start -> Finish
                    score = 1
                }
            }
            """
        )


if __name__ == "__main__":
    unittest.main()
