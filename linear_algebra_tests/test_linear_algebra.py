import math
import unittest

from computation_model_tests.math_ops import (
    determinant,
    inverse_2x2,
    lu_2x2,
    matmul,
    qr_2x2,
    singular_values_diagonal,
)
from computation_model_tests.model import MathState, MathTransition, run_procedure


class LinearAlgebraValidation(unittest.TestCase):
    def solve(self, matrix, relation, effect):
        transition = MathTransition("matrix-operation", "Matrix", "Solved", relation, effect)
        return run_procedure(MathState.create("Matrix", {"matrix": matrix}), "Solved", (transition,))[1]

    def test_matrix_multiplication(self):
        result = self.solve(
            [[1, 2], [3, 4]],
            "MatrixMultiply",
            lambda d: {"matrix": matmul(d["matrix"], [[2, 0], [1, 2]])},
        )
        self.assertEqual(result.final_state.data["matrix"], [[4, 4], [10, 8]])

    def test_determinant_and_inverse(self):
        matrix = [[4, 7], [2, 6]]
        result = self.solve(
            matrix,
            "Invert",
            lambda d: {
                "determinant": determinant(d["matrix"]),
                "inverse": inverse_2x2(d["matrix"]),
            },
        )
        self.assertEqual(result.final_state.data["determinant"], 10)
        self.assertEqual(result.final_state.data["inverse"], [[0.6, -0.7], [-0.2, 0.4]])

    def test_eigenvalues_and_eigenvectors(self):
        result = self.solve(
            [[2, 0], [0, 3]],
            "Eigendecompose",
            lambda _d: {
                "eigenvalues": [2, 3],
                "eigenvectors": [[1, 0], [0, 1]],
            },
        )
        self.assertEqual(result.final_state.data["eigenvalues"], [2, 3])

    def test_lu_decomposition(self):
        result = self.solve(
            [[4, 3], [6, 3]],
            "LUDecompose",
            lambda d: dict(zip(("L", "U"), lu_2x2(d["matrix"]))),
        )
        data = result.final_state.data
        self.assertEqual(matmul(data["L"], data["U"]), [[4, 3], [6, 3]])

    def test_qr_decomposition(self):
        matrix = [[1, 1], [1, -1]]
        result = self.solve(
            matrix,
            "QRDecompose",
            lambda d: dict(zip(("Q", "R"), qr_2x2(d["matrix"]))),
        )
        reconstructed = matmul(result.final_state.data["Q"], result.final_state.data["R"])
        for actual_row, expected_row in zip(reconstructed, matrix):
            for actual, expected in zip(actual_row, expected_row):
                self.assertTrue(math.isclose(actual, expected, abs_tol=1e-9))

    def test_svd(self):
        result = self.solve(
            [[3, 0], [0, -2]],
            "SingularValueDecompose",
            lambda d: {
                "U": [[1, 0], [0, -1]],
                "singular_values": singular_values_diagonal(d["matrix"]),
                "Vt": [[1, 0], [0, 1]],
            },
        )
        self.assertEqual(result.final_state.data["singular_values"], [3, 2])


if __name__ == "__main__":
    unittest.main()
