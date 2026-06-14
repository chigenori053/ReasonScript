import unittest

from computation_model_tests.math_ops import integrate_power
from computation_model_tests.model import MathState, MathTransition, run_procedure


class CalculusValidation(unittest.TestCase):
    def solve(self, data, relation, effect):
        transition = MathTransition("calculate", "Input", "Solved", relation, effect)
        return run_procedure(MathState.create("Input", data), "Solved", (transition,))[1]

    def test_differentiation(self):
        result = self.solve(
            {"coefficient": 1, "power": 2},
            "Differentiate",
            lambda d: {
                "coefficient": d["coefficient"] * d["power"],
                "power": d["power"] - 1,
                "symbolic": "2x",
            },
        )
        self.assertEqual(result.final_state.data["symbolic"], "2x")

    def test_partial_differentiation(self):
        result = self.solve(
            {"expression": "x^2*y+y^3", "variable": "x"},
            "PartialDifferentiate",
            lambda _d: {"symbolic": "2xy"},
        )
        self.assertEqual(result.final_state.data["symbolic"], "2xy")

    def test_indefinite_integration(self):
        result = self.solve(
            {"coefficient": 1, "power": 2},
            "Integrate",
            lambda d: {
                "term": str(integrate_power(d["coefficient"], d["power"])[0]),
                "power": integrate_power(d["coefficient"], d["power"])[1],
                "symbolic": "x^3/3+C",
            },
        )
        self.assertEqual(result.final_state.data["symbolic"], "x^3/3+C")

    def test_multiple_integration(self):
        rules = (
            MathTransition(
                "integrate-x", "Input", "AfterX", "Integrate", lambda _d: {"symbolic": "x^2*y/2"}
            ),
            MathTransition(
                "integrate-y",
                "AfterX",
                "Solved",
                "Integrate",
                lambda _d: {"symbolic": "x^2*y^2/4+C"},
            ),
        )
        plan, result = run_procedure(MathState.create("Input", {"symbolic": "xy"}), "Solved", rules)
        self.assertEqual(len(plan.selected_steps), 2)
        self.assertEqual(result.final_state.data["symbolic"], "x^2*y^2/4+C")

    def test_ordinary_differential_equation(self):
        result = self.solve(
            {"equation": "dy/dx=y"},
            "SolveODE",
            lambda _d: {"family": "y=C*e^x"},
        )
        self.assertEqual(result.final_state.data["family"], "y=C*e^x")


if __name__ == "__main__":
    unittest.main()
