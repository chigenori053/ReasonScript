import unittest

from computation_model_tests.model import MathState, MathTransition, project, run_procedure


class OutputPolicyValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rule = MathTransition(
            "approximate-sqrt-two",
            "Input",
            "Solved",
            "SquareRoot",
            lambda _d: {
                "numeric": 2**0.5,
                "rational": "99/70",
                "symbolic": "sqrt(2)",
            },
        )
        cls.plan, cls.result = run_procedure(
            MathState.create("Input", {"radicand": 2}), "Solved", (rule,)
        )

    def test_cm_op1_numeric_output(self):
        self.assertAlmostEqual(project(self.result, "numeric"), 1.41421356237)

    def test_cm_op2_rational_output(self):
        self.assertEqual(project(self.result, "rational"), "99/70")

    def test_cm_op3_symbolic_output(self):
        self.assertEqual(project(self.result, "symbolic"), "sqrt(2)")

    def test_cm_op4_state_output(self):
        self.assertEqual(project(self.result, "state"), {"state_id": "Solved"})

    def test_cm_op5_proof_output(self):
        self.assertEqual(
            project(self.result, "proof"),
            [
                {
                    "transition_id": "approximate-sqrt-two",
                    "before": "Input",
                    "after": "Solved",
                }
            ],
        )

    def test_projection_does_not_change_computation_semantics(self):
        baseline = self.result
        for policy in ("numeric", "rational", "symbolic", "state", "proof"):
            project(self.result, policy)
            self.assertEqual(self.result, baseline)


if __name__ == "__main__":
    unittest.main()
