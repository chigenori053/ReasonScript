"""Phase 10's minimal SVD foundation (`frontend/tensor/linalg.py`).

No SVD/eigendecomposition/Tucker decomposition existed anywhere in this
repository before this module, on either side (Python or Rust) -- unlike
every other primitive added in this modernization effort, there is no
existing implementation to port from or run the usual subprocess-level
Python/Rust differential test against (`svd` isn't wired into the
`tensor.*` IR/CLI surface at all; see `linalg.py`'s module docstring for
why). Correctness is instead established independently on each side
against the same closed-form values and mathematical invariants
(reconstruction, orthogonality) -- this file and
`ReasonRuntime/crates/tensor-core/src/linalg.rs`'s own
`#[cfg(test)]` module deliberately use the *same* input matrices, so a
divergence between the two implementations would show up as one side's
test failing to match the shared expected values, even without a
process-level differential harness.
"""

from __future__ import annotations

import math
import random
import unittest

from frontend.tensor.linalg import svd


def _reconstruct(u: list[list[float]], s: list[float], v: list[list[float]]) -> list[list[float]]:
    rows = len(u)
    cols = len(v)
    k = len(s)
    return [
        [sum(u[i][t] * s[t] * v[j][t] for t in range(k)) for j in range(cols)]
        for i in range(rows)
    ]


def _max_abs_diff(a: list[list[float]], b: list[list[float]]) -> float:
    return max(abs(a[i][j] - b[i][j]) for i in range(len(a)) for j in range(len(a[0])))


def _columns_orthonormal(matrix: list[list[float]], columns: int) -> float:
    rows = len(matrix)
    worst = 0.0
    for p in range(columns):
        for q in range(columns):
            dot = sum(matrix[i][p] * matrix[i][q] for i in range(rows))
            expected = 1.0 if p == q else 0.0
            worst = max(worst, abs(dot - expected))
    return worst


class SvdClosedFormTests(unittest.TestCase):
    def test_matches_known_singular_values_rank_deficient_matrix(self):
        # [[3,0],[4,0]]: column space is a line through (3,4), norm 5;
        # the second column is all zero -- singular values 5, 0.
        _u, s, _v = svd([[3.0, 0.0], [4.0, 0.0]])
        self.assertAlmostEqual(s[0], 5.0, places=9)
        self.assertAlmostEqual(s[1], 0.0, places=9)

    def test_matches_known_singular_values_diagonal_matrix(self):
        _u, s, _v = svd([[3.0, 0.0], [0.0, 2.0]])
        self.assertAlmostEqual(s[0], 3.0, places=9)
        self.assertAlmostEqual(s[1], 2.0, places=9)

    def test_identity_matrix_has_unit_singular_values_and_identity_factors(self):
        u, s, v = svd([[1.0, 0.0], [0.0, 1.0]])
        self.assertAlmostEqual(s[0], 1.0, places=9)
        self.assertAlmostEqual(s[1], 1.0, places=9)
        recon = _reconstruct(u, s, v)
        self.assertLess(_max_abs_diff(recon, [[1.0, 0.0], [0.0, 1.0]]), 1e-9)


class SvdInvariantTests(unittest.TestCase):
    def test_reconstruction_matches_original_for_random_rectangular_matrices(self):
        rng = random.Random(1)
        for rows, cols in [(3, 3), (5, 2), (2, 5), (1, 4), (4, 1), (6, 6)]:
            matrix = [[rng.uniform(-3.0, 3.0) for _ in range(cols)] for _ in range(rows)]
            u, s, v = svd(matrix)
            recon = _reconstruct(u, s, v)
            self.assertLess(
                _max_abs_diff(matrix, recon),
                1e-8,
                f"shape ({rows},{cols}) reconstruction mismatch",
            )

    def test_singular_values_are_sorted_descending(self):
        rng = random.Random(2)
        matrix = [[rng.uniform(-5.0, 5.0) for _ in range(4)] for _ in range(4)]
        _u, s, _v = svd(matrix)
        self.assertEqual(s, sorted(s, reverse=True))

    def test_singular_values_are_never_negative(self):
        rng = random.Random(3)
        matrix = [[rng.uniform(-5.0, 5.0) for _ in range(5)] for _ in range(3)]
        _u, s, _v = svd(matrix)
        self.assertTrue(all(value >= 0.0 for value in s))

    def test_u_and_v_columns_are_orthonormal(self):
        matrix = [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
            [10.0, 11.0, 12.5],
        ]
        u, s, v = svd(matrix)
        k = len(s)
        self.assertLess(_columns_orthonormal(u, k), 1e-8)
        self.assertLess(_columns_orthonormal(v, k), 1e-8)

    def test_singular_values_match_norm_for_rank_one_matrix(self):
        # A rank-1 matrix outer(a, b) has exactly one non-zero singular
        # value, equal to |a| * |b|.
        a = [2.0, -3.0, 1.0]
        b = [1.0, 4.0]
        matrix = [[a[i] * b[j] for j in range(2)] for i in range(3)]
        _u, s, _v = svd(matrix)
        expected = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
        self.assertAlmostEqual(s[0], expected, places=8)
        self.assertAlmostEqual(s[1], 0.0, places=8)


class SvdErrorTests(unittest.TestCase):
    def test_empty_matrix_is_rejected(self):
        with self.assertRaises(ValueError) as raised:
            svd([])
        self.assertIn("LINALG-001", str(raised.exception))

    def test_ragged_matrix_is_rejected(self):
        with self.assertRaises(ValueError) as raised:
            svd([[1.0, 2.0], [3.0]])
        self.assertIn("LINALG-001", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
