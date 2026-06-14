"""Small deterministic mathematical operations used as validation witnesses."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Iterable


Matrix = list[list[float]]


def matmul(left: Matrix, right: Matrix) -> Matrix:
    return [
        [sum(a * b for a, b in zip(row, column)) for column in zip(*right)]
        for row in left
    ]


def determinant(matrix: Matrix) -> float:
    if len(matrix) == 1:
        return matrix[0][0]
    return sum(
        ((-1) ** column)
        * matrix[0][column]
        * determinant(
            [
                [value for index, value in enumerate(row) if index != column]
                for row in matrix[1:]
            ]
        )
        for column in range(len(matrix))
    )


def inverse_2x2(matrix: Matrix) -> Matrix:
    det = determinant(matrix)
    if det == 0:
        raise ValueError("singular matrix")
    a, b = matrix[0]
    c, d = matrix[1]
    return [[d / det, -b / det], [-c / det, a / det]]


def lu_2x2(matrix: Matrix) -> tuple[Matrix, Matrix]:
    a, b = matrix[0]
    c, d = matrix[1]
    multiplier = c / a
    return [[1, 0], [multiplier, 1]], [[a, b], [0, d - multiplier * b]]


def qr_2x2(matrix: Matrix) -> tuple[Matrix, Matrix]:
    first = [matrix[0][0], matrix[1][0]]
    second = [matrix[0][1], matrix[1][1]]
    norm = math.hypot(*first)
    q1 = [value / norm for value in first]
    projection = sum(a * b for a, b in zip(q1, second))
    orthogonal = [value - projection * basis for value, basis in zip(second, q1)]
    orthogonal_norm = math.hypot(*orthogonal)
    q2 = [value / orthogonal_norm for value in orthogonal]
    q = [[q1[0], q2[0]], [q1[1], q2[1]]]
    r = matmul([[q[0][0], q[1][0]], [q[0][1], q[1][1]]], matrix)
    return q, r


def singular_values_diagonal(matrix: Matrix) -> list[float]:
    return sorted((abs(matrix[0][0]), abs(matrix[1][1])), reverse=True)


def polynomial_roots(coefficients: Iterable[int]) -> list[int]:
    coefficients = list(coefficients)
    constant = coefficients[-1]
    candidates = range(-abs(constant), abs(constant) + 1)

    def evaluate(x: int) -> int:
        value = 0
        for coefficient in coefficients:
            value = value * x + coefficient
        return value

    return [candidate for candidate in candidates if candidate and evaluate(candidate) == 0]


def integrate_power(coefficient: int, power: int) -> tuple[Fraction, int]:
    return Fraction(coefficient, power + 1), power + 1
