import unittest

from computation_model_tests.math_ops import polynomial_roots
from computation_model_tests.model import MathState, MathTransition, run_procedure


class AdvancedAlgebraValidation(unittest.TestCase):
    def run_one(self, data, transition):
        return run_procedure(MathState.create("Input", data), "Solved", (transition,))[1]

    def test_polynomial_expansion(self):
        result = self.run_one(
            {"factors": [1, 2, 3]},
            MathTransition(
                "expand-product",
                "Input",
                "Solved",
                "PolynomialExpansion",
                lambda d: {"coefficients": [1, sum(d["factors"]), 11, 6]},
            ),
        )
        self.assertEqual(result.final_state.data["coefficients"], [1, 6, 11, 6])

    def test_polynomial_factorization_and_cubic_roots(self):
        result = self.run_one(
            {"coefficients": [1, -6, 11, -6]},
            MathTransition(
                "factor-cubic",
                "Input",
                "Solved",
                "PolynomialFactorization",
                lambda d: {
                    "roots": polynomial_roots(d["coefficients"]),
                    "factorization": "(x-1)(x-2)(x-3)",
                },
            ),
        )
        self.assertEqual(result.final_state.data["roots"], [1, 2, 3])

    def test_quartic_equation(self):
        result = self.run_one(
            {"expression": "x^4-5x^2+4"},
            MathTransition(
                "factor-biquadratic",
                "Input",
                "Solved",
                "QuarticEquation",
                lambda _d: {"roots": [-2, -1, 1, 2]},
            ),
        )
        self.assertEqual(result.final_state.data["roots"], [-2, -1, 1, 2])

    def test_complex_numbers(self):
        result = self.run_one(
            {"expression": "x^2+1=0"},
            MathTransition(
                "solve-over-complex",
                "Input",
                "Solved",
                "ComplexRoots",
                lambda _d: {"roots": ["-i", "i"]},
            ),
        )
        self.assertEqual(result.final_state.data["roots"], ["-i", "i"])

    def test_rational_function_simplification(self):
        result = self.run_one(
            {"numerator": "x^2-1", "denominator": "x-1", "domain_exclusions": [1]},
            MathTransition(
                "cancel-common-factor",
                "Input",
                "Solved",
                "RationalSimplification",
                lambda d: {
                    "expression": "x+1",
                    "domain_exclusions": d["domain_exclusions"],
                },
            ),
        )
        self.assertEqual(
            result.final_state.data,
            {"expression": "x+1", "domain_exclusions": [1]},
        )


if __name__ == "__main__":
    unittest.main()
