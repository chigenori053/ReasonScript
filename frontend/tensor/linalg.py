"""Minimal SVD foundation (Phase 10, "Approximate Tensor Logic" scope,
narrowed to rank-2 matrices only after an explicit scope decision).

No SVD/eigendecomposition/Tucker decomposition existed anywhere in this
repository before this module -- unlike every other `optimizer.*`/
`relation.*` primitive added so far, there is nothing existing to
compose this from (those were built from existing elementwise/
comparison primitives; a correct SVD needs a real linear-algebra
algorithm). This is deliberately internal infrastructure, not wired
into the `tensor.*` language surface yet: a full SVD naturally produces
three differently-shaped outputs (`U`, singular values, `V`), which
would hit the same "no synthetic struct return type" problem
`frontend/tensor/optimizers.py` documents for `optimizer.*` -- solving
that (and everything else a real `@approximate(method="tucker", ...)`
Tucker decomposition needs: mode-n unfolding/refolding, N-way core
tensor computation, a rank-selection/tolerance policy) is real,
separate, follow-up work, not attempted here.

Algorithm: one-sided Jacobi SVD (Hestenes' method) -- computes
``A = U @ diag(S) @ V.T`` for an arbitrary ``m x n`` real matrix by
repeatedly rotating pairs of columns of a working copy of `A` toward
orthogonality (accumulating the rotations into `V`), until the target
Gram matrix's off-diagonal terms fall below `tol`, or `max_sweeps` sweeps
have run. This particular algorithm was chosen (over e.g. eigendecomposing
`A.T @ A`) because it is numerically well-conditioned -- it never
squares the matrix's condition number -- while still being simple
enough to implement, verify, and reason about correctly with no
existing implementation in this codebase to port from or differentially
test against; correctness here is established by direct verification
against closed-form examples and reconstruction/orthogonality
invariants instead (see `tensor_standard_functions_tests/test_linalg_svd.py`).
"""

from __future__ import annotations

import math


def svd(
    matrix: list[list[float]],
    *,
    max_sweeps: int = 60,
    tol: float = 1e-14,
) -> tuple[list[list[float]], list[float], list[list[float]]]:
    """Returns ``(U, singular_values, V)`` such that
    ``matrix ≈ U @ diag(singular_values) @ transpose(V)``.

    `U` is `m x k`, `V` is `n x k` (both column-orthonormal), and
    `singular_values` has length `k = min(m, n)`, sorted descending --
    the conventional SVD shape/ordering convention. `matrix` must be
    non-empty and rectangular (every row the same length); raises
    `ValueError` otherwise.
    """
    rows = len(matrix)
    if rows == 0:
        raise ValueError("LINALG-001 svd requires a non-empty matrix")
    cols = len(matrix[0])
    if cols == 0 or any(len(row) != cols for row in matrix):
        raise ValueError("LINALG-001 svd requires a non-empty rectangular matrix")

    transposed = cols > rows
    if transposed:
        working = [[matrix[i][j] for i in range(rows)] for j in range(cols)]
        m, n = cols, rows
    else:
        working = [list(row) for row in matrix]
        m, n = rows, cols

    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _sweep in range(max_sweeps):
        off_diagonal_energy = 0.0
        for p in range(n):
            for q in range(p + 1, n):
                alpha = sum(working[i][p] ** 2 for i in range(m))
                beta = sum(working[i][q] ** 2 for i in range(m))
                gamma = sum(working[i][p] * working[i][q] for i in range(m))
                off_diagonal_energy += gamma * gamma
                if abs(gamma) < tol * math.sqrt(alpha * beta + 1e-300):
                    continue
                zeta = (beta - alpha) / (2 * gamma)
                t = (1.0 if zeta >= 0 else -1.0) / (abs(zeta) + math.sqrt(1.0 + zeta * zeta))
                c = 1.0 / math.sqrt(1.0 + t * t)
                s = c * t
                for i in range(m):
                    a_p, a_q = working[i][p], working[i][q]
                    working[i][p] = c * a_p - s * a_q
                    working[i][q] = s * a_p + c * a_q
                for i in range(n):
                    v_p, v_q = v[i][p], v[i][q]
                    v[i][p] = c * v_p - s * v_q
                    v[i][q] = s * v_p + c * v_q
        if off_diagonal_energy < tol * tol:
            break

    singular_values = []
    u = [[0.0] * n for _ in range(m)]
    for j in range(n):
        sigma = math.sqrt(sum(working[i][j] ** 2 for i in range(m)))
        singular_values.append(sigma)
        if sigma > 1e-300:
            for i in range(m):
                u[i][j] = working[i][j] / sigma

    order = sorted(range(n), key=lambda j: -singular_values[j])
    singular_values = [singular_values[j] for j in order]
    u = [[u[i][j] for j in order] for i in range(m)]
    v = [[v[i][j] for j in order] for i in range(n)]

    if transposed:
        u, v = v, u

    return u, singular_values, v
