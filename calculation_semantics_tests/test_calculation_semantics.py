import unittest

from calculation_semantics_tests.model import (
    CalculationError,
    lower_program,
    parse_calculations,
)


class CalculationSemanticsIntegrationTests(unittest.TestCase):
    def test_full_surface_ast_ir_reason_ir_plan_pipeline_is_deterministic(self):
        source = """
        pub calculation Area goal:value {
            let width = 10
            let height = 20
            result = width * height
        }
        pub calculation Cost goal:value {
            result = Area * 100
        }
        """
        ast = parse_calculations(source)
        self.assertEqual(ast, parse_calculations(source))
        self.assertEqual(lower_program(ast), lower_program(ast))

    def test_every_calculation_has_exactly_one_result_state(self):
        lowered = lower_program(
            parse_calculations(
                """
                pub calculation A goal:value {
                    result = 1 + 2
                }
                pub calculation B goal:value {
                    result = A * 3
                }
                """
            )
        )
        self.assertEqual(
            [item.result_state for item in lowered.calculations],
            ["A.state.result", "B.state.result"],
        )

    def test_missing_or_duplicate_result_is_rejected(self):
        for body in ("let x = 1", "result = 1\nresult = 2"):
            with self.subTest(body=body), self.assertRaises(CalculationError):
                parse_calculations(
                    f"""
                    pub calculation Invalid goal:value {{
                        {body}
                    }}
                    """
                )


if __name__ == "__main__":
    unittest.main()
