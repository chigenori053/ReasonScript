import unittest

from frontend.language_surface import SurfaceSyntaxError, compile_program, execution_plan_for, parse


def _compile(source: str):
    reason_ir = compile_program(parse(source))[0]
    return reason_ir, execution_plan_for(reason_ir)


class CalculationDependencyLoweringTests(unittest.TestCase):
    def test_cdl_001_single_calculation(self):
        reason_ir, plan = _compile(
            """
            module Test {
              calculation A {
                result = 10
              }
            }
            """
        )

        self.assertEqual(len(reason_ir["transitions"]), 1)
        self.assertEqual(len(plan["selected_steps"]), 1)
        self.assertEqual(reason_ir["goal"], {"kind": "reach_state", "target": "A.state.result"})

    def test_cdl_002_undefined_reference(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-020 undefined variable"):
            parse(
                """
                module Test {
                  calculation B {
                    result = Unknown * 2
                  }
                }
                """
            )

    def test_cdl_003_direct_dependency(self):
        reason_ir, plan = _compile(
            """
            module Test {
              calculation A {
                result = 10
              }

              calculation B {
                result = A * 2
              }
            }
            """
        )

        self.assertEqual(reason_ir["metadata"]["calculation_order"], ["A", "B"])
        self.assertEqual(
            reason_ir["metadata"]["calculation_dependencies"],
            [{"source": "A", "target": "B"}],
        )
        self.assertEqual(
            [(item["source"], item["target"]) for item in reason_ir["transitions"]],
            [("TestStart", "A.state.result"), ("A.state.result", "B.state.result")],
        )
        self.assertEqual(
            [item["transition_id"] for item in plan["selected_steps"]],
            ["A-1-result", "B-1-result"],
        )

    def test_cdl_004_multi_dependency(self):
        reason_ir, plan = _compile(
            """
            module Test {
              calculation Width {
                result = 10
              }

              calculation Height {
                result = 20
              }

              calculation Area {
                result = Width * Height
              }
            }
            """
        )

        self.assertEqual(reason_ir["metadata"]["calculation_order"], ["Height", "Width", "Area"])
        self.assertEqual(
            reason_ir["metadata"]["calculation_dependencies"],
            [
                {"source": "Height", "target": "Area"},
                {"source": "Width", "target": "Area"},
            ],
        )
        self.assertEqual(
            [(item["source"], item["target"]) for item in reason_ir["transitions"]],
            [
                ("TestStart", "Height.state.result"),
                ("Height.state.result", "Width.state.result"),
                ("Width.state.result", "Area.state.result"),
            ],
        )
        self.assertEqual(len(plan["selected_steps"]), 3)

    def test_cdl_005_deep_dependency_chain(self):
        reason_ir, plan = _compile(
            """
            module Test {
              calculation A {
                result = 10
              }

              calculation B {
                result = A * 2
              }

              calculation C {
                result = B + 5
              }
            }
            """
        )

        self.assertEqual(reason_ir["metadata"]["calculation_order"], ["A", "B", "C"])
        self.assertEqual(
            [(item["source"], item["target"]) for item in reason_ir["transitions"]],
            [
                ("TestStart", "A.state.result"),
                ("A.state.result", "B.state.result"),
                ("B.state.result", "C.state.result"),
            ],
        )
        self.assertEqual(len(plan["selected_steps"]), 3)

    def test_cdl_006_dependency_cycle(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-030 Dependency Cycle Detected"):
            parse(
                """
                module Test {
                  calculation A {
                    result = B + 1
                  }

                  calculation B {
                    result = A + 1
                  }
                }
                """
            )

    def test_cdl_007_diamond_dependency(self):
        reason_ir, plan = _compile(
            """
            module Test {
              calculation A {
                result = 10
              }

              calculation B {
                result = A + 1
              }

              calculation C {
                result = A + 2
              }

              calculation D {
                result = B + C
              }
            }
            """
        )

        self.assertEqual(reason_ir["metadata"]["calculation_order"], ["A", "B", "C", "D"])
        self.assertEqual(
            reason_ir["metadata"]["calculation_dependencies"],
            [
                {"source": "A", "target": "B"},
                {"source": "A", "target": "C"},
                {"source": "B", "target": "D"},
                {"source": "C", "target": "D"},
            ],
        )
        self.assertEqual(
            [item["transition_id"] for item in plan["selected_steps"]],
            ["A-1-result", "B-1-result", "C-1-result", "D-1-result"],
        )


if __name__ == "__main__":
    unittest.main()
