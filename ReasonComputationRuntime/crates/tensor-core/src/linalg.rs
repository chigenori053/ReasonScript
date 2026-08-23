//! Minimal SVD foundation (Phase 10, "Approximate Tensor Logic" scope,
//! narrowed to rank-2 matrices only after an explicit scope decision).
//! Mirrors `frontend/tensor/linalg.py` exactly (same one-sided Jacobi
//! algorithm, same variable names where practical) -- see that module's
//! docstring for the full rationale: no SVD/eigendecomposition/Tucker
//! decomposition existed anywhere in this repository before this, on
//! either side, so there is nothing to port from or differentially test
//! against; correctness is established directly (closed-form examples,
//! reconstruction/orthogonality invariants) on both sides independently,
//! then cross-checked against each other.
//!
//! Deliberately internal infrastructure: not wired into the `tensor.*`
//! IR/dispatch surface (`tensor_dispatch.rs`) yet. A full SVD naturally
//! produces three differently-shaped outputs (`U`, singular values,
//! `V`), which would hit the same "no synthetic struct return type"
//! problem `optimizer_dispatch.rs`'s module doc describes for
//! `optimizer.*` -- solving that, and everything else a real
//! `@approximate(method="tucker", ...)` Tucker decomposition needs
//! (mode-n unfolding/refolding, N-way core tensor computation, a
//! rank-selection/tolerance policy), is real, separate, follow-up work.

use crate::error::{Result, TensorCoreError};
use crate::store::TensorData;

#[derive(Debug)]
pub struct SvdResult {
    /// `rows x k`, column-orthonormal.
    pub u: TensorData,
    /// Length `k = min(rows, cols)`, sorted descending.
    pub singular_values: Vec<f64>,
    /// `cols x k`, column-orthonormal (`V`, not `V^T`).
    pub v: TensorData,
}

/// `matrix ≈ U @ diag(singular_values) @ V^T`. `matrix` must be a
/// rank-2 `TensorData` (any dtype -- computed in `f64` regardless,
/// matching every other op in this crate's `compat-reference` numeric
/// mode); returns `LINALG-001` otherwise.
pub fn svd(matrix: &TensorData, max_sweeps: usize, tol: f64) -> Result<SvdResult> {
    if matrix.shape.len() != 2 {
        return Err(TensorCoreError::new(
            "LINALG-001",
            "svd requires a rank-2 matrix",
        ));
    }
    let (rows, cols) = (matrix.shape[0], matrix.shape[1]);
    if rows == 0 || cols == 0 {
        return Err(TensorCoreError::new(
            "LINALG-001",
            "svd requires a non-empty matrix",
        ));
    }

    let transposed = cols > rows;
    let (m, n, mut working) = if transposed {
        let mut t = vec![0.0; cols * rows];
        for i in 0..rows {
            for j in 0..cols {
                t[j * rows + i] = matrix.data[i * cols + j];
            }
        }
        (cols, rows, t)
    } else {
        (rows, cols, matrix.data.clone())
    };
    // `working` is row-major `m x n` throughout, matching `TensorData`'s
    // own layout convention.

    let mut v = vec![0.0; n * n];
    for i in 0..n {
        v[i * n + i] = 1.0;
    }

    for _sweep in 0..max_sweeps {
        let mut off_diagonal_energy = 0.0;
        for p in 0..n {
            for q in (p + 1)..n {
                let mut alpha = 0.0;
                let mut beta = 0.0;
                let mut gamma = 0.0;
                for i in 0..m {
                    let a_p = working[i * n + p];
                    let a_q = working[i * n + q];
                    alpha += a_p * a_p;
                    beta += a_q * a_q;
                    gamma += a_p * a_q;
                }
                off_diagonal_energy += gamma * gamma;
                if gamma.abs() < tol * (alpha * beta + 1e-300).sqrt() {
                    continue;
                }
                let zeta = (beta - alpha) / (2.0 * gamma);
                let t = zeta.signum() / (zeta.abs() + (1.0 + zeta * zeta).sqrt());
                let c = 1.0 / (1.0 + t * t).sqrt();
                let s = c * t;
                for i in 0..m {
                    let a_p = working[i * n + p];
                    let a_q = working[i * n + q];
                    working[i * n + p] = c * a_p - s * a_q;
                    working[i * n + q] = s * a_p + c * a_q;
                }
                for i in 0..n {
                    let v_p = v[i * n + p];
                    let v_q = v[i * n + q];
                    v[i * n + p] = c * v_p - s * v_q;
                    v[i * n + q] = s * v_p + c * v_q;
                }
            }
        }
        if off_diagonal_energy < tol * tol {
            break;
        }
    }

    let mut singular_values = vec![0.0; n];
    let mut u = vec![0.0; m * n];
    for j in 0..n {
        let mut sum_sq = 0.0;
        for i in 0..m {
            sum_sq += working[i * n + j] * working[i * n + j];
        }
        let sigma = sum_sq.sqrt();
        singular_values[j] = sigma;
        if sigma > 1e-300 {
            for i in 0..m {
                u[i * n + j] = working[i * n + j] / sigma;
            }
        }
    }

    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&a, &b| singular_values[b].partial_cmp(&singular_values[a]).unwrap());
    let sorted_singular_values: Vec<f64> = order.iter().map(|&j| singular_values[j]).collect();
    let mut sorted_u = vec![0.0; m * n];
    let mut sorted_v = vec![0.0; n * n];
    for (new_j, &old_j) in order.iter().enumerate() {
        for i in 0..m {
            sorted_u[i * n + new_j] = u[i * n + old_j];
        }
        for i in 0..n {
            sorted_v[i * n + new_j] = v[i * n + old_j];
        }
    }

    let (final_u, final_u_shape, final_v, final_v_shape) = if transposed {
        (sorted_v, vec![n, n], sorted_u, vec![m, n])
    } else {
        (sorted_u, vec![m, n], sorted_v, vec![n, n])
    };

    Ok(SvdResult {
        u: TensorData {
            shape: final_u_shape,
            dtype: crate::dtype::Dtype::F64,
            data: final_u,
        },
        singular_values: sorted_singular_values,
        v: TensorData {
            shape: final_v_shape,
            dtype: crate::dtype::Dtype::F64,
            data: final_v,
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dtype::Dtype;

    fn matrix(rows: usize, cols: usize, data: Vec<f64>) -> TensorData {
        TensorData {
            shape: vec![rows, cols],
            dtype: Dtype::F64,
            data,
        }
    }

    fn reconstruct(result: &SvdResult, rows: usize, cols: usize) -> Vec<f64> {
        let k = result.singular_values.len();
        let mut out = vec![0.0; rows * cols];
        for i in 0..rows {
            for j in 0..cols {
                let mut sum = 0.0;
                for t in 0..k {
                    sum += result.u.data[i * k + t] * result.singular_values[t] * result.v.data[j * k + t];
                }
                out[i * cols + j] = sum;
            }
        }
        out
    }

    #[test]
    fn matches_known_closed_form_singular_values() {
        // [[3,0],[4,0]] has singular values 5, 0 (column space is a
        // line through (3,4), norm 5; the second column is all zero).
        let a = matrix(2, 2, vec![3.0, 0.0, 4.0, 0.0]);
        let result = svd(&a, 60, 1e-14).unwrap();
        assert!((result.singular_values[0] - 5.0).abs() < 1e-9);
        assert!(result.singular_values[1].abs() < 1e-9);

        // A diagonal matrix's singular values are its diagonal entries
        // (sorted descending) -- diag(3, 2).
        let diag = matrix(2, 2, vec![3.0, 0.0, 0.0, 2.0]);
        let result = svd(&diag, 60, 1e-14).unwrap();
        assert!((result.singular_values[0] - 3.0).abs() < 1e-9);
        assert!((result.singular_values[1] - 2.0).abs() < 1e-9);
    }

    #[test]
    fn reconstructs_random_rectangular_matrices() {
        // A small deterministic PRNG (no external crate) covering
        // square, tall, and wide shapes.
        let mut state: u64 = 88172645463325252;
        let mut next = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            ((state >> 11) as f64 / (1u64 << 53) as f64) * 6.0 - 3.0
        };
        for &(rows, cols) in &[(3usize, 3usize), (5, 2), (2, 5), (1, 4), (4, 1)] {
            let data: Vec<f64> = (0..rows * cols).map(|_| next()).collect();
            let a = matrix(rows, cols, data.clone());
            let result = svd(&a, 100, 1e-14).unwrap();
            let recon = reconstruct(&result, rows, cols);
            for (original, reconstructed) in data.iter().zip(recon.iter()) {
                assert!(
                    (original - reconstructed).abs() < 1e-8,
                    "shape ({rows},{cols}): {original} vs {reconstructed}"
                );
            }
            assert_eq!(
                result.singular_values,
                {
                    let mut sorted = result.singular_values.clone();
                    sorted.sort_by(|a, b| b.partial_cmp(a).unwrap());
                    sorted
                },
                "singular values must be sorted descending"
            );
        }
    }

    #[test]
    fn u_and_v_columns_are_orthonormal() {
        let a = matrix(4, 3, vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.5]);
        let result = svd(&a, 100, 1e-14).unwrap();
        let k = result.singular_values.len();
        for p in 0..k {
            for q in 0..k {
                let mut dot = 0.0;
                for i in 0..4 {
                    dot += result.u.data[i * k + p] * result.u.data[i * k + q];
                }
                let expected = if p == q { 1.0 } else { 0.0 };
                assert!((dot - expected).abs() < 1e-8, "U columns {p},{q}: {dot}");
            }
        }
        for p in 0..k {
            for q in 0..k {
                let mut dot = 0.0;
                for i in 0..3 {
                    dot += result.v.data[i * k + p] * result.v.data[i * k + q];
                }
                let expected = if p == q { 1.0 } else { 0.0 };
                assert!((dot - expected).abs() < 1e-8, "V columns {p},{q}: {dot}");
            }
        }
    }

    #[test]
    fn rejects_non_matrix_shapes() {
        let vector = TensorData {
            shape: vec![3],
            dtype: Dtype::F64,
            data: vec![1.0, 2.0, 3.0],
        };
        assert_eq!(svd(&vector, 60, 1e-14).unwrap_err().code, "LINALG-001");
    }
}
