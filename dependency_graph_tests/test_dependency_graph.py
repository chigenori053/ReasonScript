import unittest

from calculation_semantics_tests.model import (
    DependencyCycleError,
    lower_program,
    parse_calculations,
)


class DependencyGraphTests(unittest.TestCase):
    def test_cs_06_reference_resolves_to_result_state_and_dependency_edge(self):
        lowered = lower_program(
            parse_calculations(
                """
                pub calculation Area goal:value {
                    let width = 10
                    let height = 20
                    result = width * height
                }
                pub calculation Cost goal:value {
                    result = Area * 100
                }
                """
            )
        )
        cost = lowered.calculations[1]
        self.assertEqual(cost.dependencies[0].source_state, "Area.state.result")
        self.assertIn("Area.result", cost.transitions[0].inputs)

    def test_cs_07_dependency_order_is_topological_and_stable(self):
        source = """
        pub calculation Decision goal:value {
            result = Cost + 1
        }
        pub calculation Area goal:value {
            result = 20 * 10
        }
        pub calculation Cost goal:value {
            result = Area * 100
        }
        """
        lowered = lower_program(parse_calculations(source))
        self.assertEqual(
            [item.calculation for item in lowered.calculations],
            ["Area", "Cost", "Decision"],
        )

    def test_cs_07_cycles_fail_before_execution_plan_generation(self):
        source = """
        pub calculation A goal:value {
            result = B + 1
        }
        pub calculation B goal:value {
            result = A + 1
        }
        """
        with self.assertRaises(DependencyCycleError):
            lower_program(parse_calculations(source))


if __name__ == "__main__":
    unittest.main()
