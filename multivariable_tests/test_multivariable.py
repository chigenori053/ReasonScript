import unittest

from computation_model_tests.model import MathState, MathTransition, run_procedure


class MultivariableValidation(unittest.TestCase):
    def solve(self, expression, relation, output):
        rule = MathTransition("transform", "Input", "Solved", relation, lambda _d: output)
        return run_procedure(MathState.create("Input", {"expression": expression}), "Solved", (rule,))[1]

    def test_gradient(self):
        result = self.solve("x^2+y^2", "Gradient", {"gradient": ["2x", "2y"]})
        self.assertEqual(result.final_state.data["gradient"], ["2x", "2y"])

    def test_jacobian(self):
        result = self.solve(
            "[x^2+y, x*y]",
            "Jacobian",
            {"jacobian": [["2x", "1"], ["y", "x"]]},
        )
        self.assertEqual(result.final_state.data["jacobian"][1], ["y", "x"])

    def test_hessian(self):
        result = self.solve(
            "x^2+x*y+y^2",
            "Hessian",
            {"hessian": [[2, 1], [1, 2]]},
        )
        self.assertEqual(result.final_state.data["hessian"], [[2, 1], [1, 2]])

    def test_optimization_as_multistep_plan(self):
        rules = (
            MathTransition(
                "compute-gradient",
                "Input",
                "StationaryEquation",
                "Gradient",
                lambda d: {"objective": d["objective"], "equation": ["2x-2=0", "2y+4=0"]},
            ),
            MathTransition(
                "solve-stationary",
                "StationaryEquation",
                "Candidate",
                "Solve",
                lambda _d: {"point": [1, -2]},
            ),
            MathTransition(
                "classify-hessian",
                "Candidate",
                "Solved",
                "ClassifyMinimum",
                lambda d: {"point": d["point"], "classification": "global minimum"},
            ),
        )
        plan, result = run_procedure(
            MathState.create("Input", {"objective": "(x-1)^2+(y+2)^2"}),
            "Solved",
            rules,
        )
        self.assertEqual(len(plan.selected_steps), 3)
        self.assertEqual(result.final_state.data["point"], [1, -2])

    def test_vector_field_divergence(self):
        result = self.solve(
            "[x^2, y^2, z^2]",
            "Divergence",
            {"symbolic": "2x+2y+2z"},
        )
        self.assertEqual(result.final_state.data["symbolic"], "2x+2y+2z")


if __name__ == "__main__":
    unittest.main()
