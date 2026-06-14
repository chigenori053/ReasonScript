import math
import unittest

from computation_model_tests.model import MathState, MathTransition, run_procedure


class TrigonometryValidation(unittest.TestCase):
    def transform(self, expression, relation, output):
        rule = MathTransition(
            "trig-transform",
            "Input",
            "Solved",
            relation,
            lambda _d: output,
        )
        return run_procedure(MathState.create("Input", {"expression": expression}), "Solved", (rule,))[1]

    def test_sine_cosine_and_tangent_evaluation(self):
        result = self.transform(
            "values(pi/4)",
            "EvaluateTrigonometry",
            {"sin": math.sin(math.pi / 4), "cos": math.cos(math.pi / 4), "tan": 1.0},
        )
        self.assertTrue(math.isclose(result.final_state.data["tan"], 1.0))

    def test_inverse_trigonometric_function(self):
        result = self.transform("arcsin(1)", "InverseTrigonometry", {"value": math.pi / 2})
        self.assertTrue(math.isclose(result.final_state.data["value"], math.pi / 2))

    def test_pythagorean_identity(self):
        result = self.transform(
            "sin^2(x)+cos^2(x)",
            "ApplyIdentity",
            {"symbolic": "1", "identity": "pythagorean"},
        )
        self.assertEqual(result.final_state.data["symbolic"], "1")

    def test_double_angle_transformation(self):
        result = self.transform(
            "sin(2x)",
            "ApplyDoubleAngle",
            {"symbolic": "2*sin(x)*cos(x)"},
        )
        self.assertEqual(result.final_state.data["symbolic"], "2*sin(x)*cos(x)")


if __name__ == "__main__":
    unittest.main()
