//! Dense CPU reference Tensor operations, matching
//! `frontend/tensor/runtime.py`'s `PythonTensorBackend` methods
//! elementwise, shape-op-for-shape-op, and reduction-for-reduction.
//!
//! The functions in this file are `NumericMode::CompatReference`'s
//! unconditional, sequential implementations -- unchanged since Phase 4
//! and untouched by Phase 9. The `_parallel` twins alongside the
//! highest-traffic ones (`broadcast_binary`/`unary`/`reduce`/`matmul`)
//! are `NumericMode::NativeFast`-only (see `tensor_dispatch.rs`'s
//! mode-based dispatch): real `rayon` parallelism, deterministic by
//! construction rather than by accident, documented per function below.

use rayon::prelude::*;

use crate::dtype::{promote, Dtype};
use crate::error::{Result, TensorCoreError};
use crate::shape::{
    all_coords, broadcast_flat_index, broadcast_shape, coords, flat_index, normalize_axis, product,
};
use crate::store::TensorData;

pub fn broadcast_binary(
    left: &TensorData,
    right: &TensorData,
    op: impl Fn(f64, f64) -> f64,
    result_dtype: Option<Dtype>,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let shape = broadcast_shape(&left.shape, &right.shape)?;
    let dtype = result_dtype.unwrap_or_else(|| promote(left.dtype, right.dtype));
    let mut data = Vec::with_capacity(product(&shape));
    for out_coords in all_coords(&shape) {
        let a = left.data[broadcast_flat_index(&out_coords, &left.shape)];
        let b = right.data[broadcast_flat_index(&out_coords, &right.shape)];
        data.push(op(a, b));
    }
    Ok((shape, dtype, data))
}

/// Elementwise, so trivially deterministic under parallelism: every
/// output position is computed independently from its own two input
/// values, and `par_iter().map(..).collect()` always preserves the
/// source order regardless of which thread finishes which element
/// first -- unlike a parallel *reduction*, there is no summation-order
/// question here at all.
pub fn broadcast_binary_parallel(
    left: &TensorData,
    right: &TensorData,
    op: impl Fn(f64, f64) -> f64 + Sync,
    result_dtype: Option<Dtype>,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let shape = broadcast_shape(&left.shape, &right.shape)?;
    let dtype = result_dtype.unwrap_or_else(|| promote(left.dtype, right.dtype));
    let data: Vec<f64> = all_coords(&shape)
        .par_iter()
        .map(|out_coords| {
            let a = left.data[broadcast_flat_index(out_coords, &left.shape)];
            let b = right.data[broadcast_flat_index(out_coords, &right.shape)];
            op(a, b)
        })
        .collect();
    Ok((shape, dtype, data))
}

pub fn comparison(
    left: &TensorData,
    right: &TensorData,
    op: impl Fn(f64, f64) -> bool,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    broadcast_binary(
        left,
        right,
        move |a, b| if op(a, b) { 1.0 } else { 0.0 },
        Some(Dtype::Bool),
    )
}

pub fn unary(
    tensor: &TensorData,
    op: impl Fn(f64) -> f64,
    result_dtype: Option<Dtype>,
) -> (Vec<usize>, Dtype, Vec<f64>) {
    let data: Vec<f64> = tensor.data.iter().map(|value| op(*value)).collect();
    (
        tensor.shape.clone(),
        result_dtype.unwrap_or(tensor.dtype),
        data,
    )
}

/// Same determinism argument as `broadcast_binary_parallel`: each output
/// element depends only on its own input element.
pub fn unary_parallel(
    tensor: &TensorData,
    op: impl Fn(f64) -> f64 + Sync,
    result_dtype: Option<Dtype>,
) -> (Vec<usize>, Dtype, Vec<f64>) {
    let data: Vec<f64> = tensor.data.par_iter().map(|value| op(*value)).collect();
    (
        tensor.shape.clone(),
        result_dtype.unwrap_or(tensor.dtype),
        data,
    )
}

pub fn reshape(tensor: &TensorData, target: &[i64]) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let inferred_count = target.iter().filter(|&&value| value == -1).count();
    if inferred_count > 1 {
        return Err(TensorCoreError::new(
            "TSF-007",
            "reshape permits at most one inferred dimension",
        ));
    }
    let mut resolved: Vec<usize> = Vec::with_capacity(target.len());
    if inferred_count == 1 {
        let known: i64 = target.iter().filter(|&&value| value != -1).product();
        if known == 0 || tensor.data.len() as i64 % known != 0 {
            return Err(TensorCoreError::new(
                "TSF-007",
                "reshape element count mismatch",
            ));
        }
        let inferred = tensor.data.len() as i64 / known;
        for &value in target {
            resolved.push(if value == -1 {
                inferred as usize
            } else {
                value as usize
            });
        }
    } else {
        resolved = target.iter().map(|&value| value as usize).collect();
    }
    if product(&resolved) != tensor.data.len() {
        return Err(TensorCoreError::new(
            "TSF-007",
            "reshape element count mismatch",
        ));
    }
    Ok((resolved, tensor.dtype, tensor.data.clone()))
}

pub fn transpose(
    tensor: &TensorData,
    axis_a: i64,
    axis_b: i64,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let rank = tensor.shape.len();
    let a = normalize_axis(axis_a, rank, false)?;
    let b = normalize_axis(axis_b, rank, false)?;
    let mut out_shape = tensor.shape.clone();
    out_shape.swap(a, b);
    let mut out = vec![0.0; tensor.data.len()];
    for (index, item) in tensor.data.iter().enumerate() {
        let mut coord = coords(index, &tensor.shape);
        coord.swap(a, b);
        out[flat_index(&coord, &out_shape)] = *item;
    }
    Ok((out_shape, tensor.dtype, out))
}

pub fn squeeze(tensor: &TensorData, axis: Option<i64>) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let shape = match axis {
        None => tensor
            .shape
            .iter()
            .copied()
            .filter(|&size| size != 1)
            .collect(),
        Some(axis) => {
            let normalized = normalize_axis(axis, tensor.shape.len(), false)?;
            if tensor.shape[normalized] != 1 {
                return Err(TensorCoreError::new(
                    "TSF-003",
                    "cannot squeeze a dimension whose size is not one",
                ));
            }
            let mut shape = tensor.shape.clone();
            shape.remove(normalized);
            shape
        }
    };
    Ok((shape, tensor.dtype, tensor.data.clone()))
}

pub fn unsqueeze(tensor: &TensorData, axis: i64) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let normalized = normalize_axis(axis, tensor.shape.len(), true)?;
    let mut shape = tensor.shape.clone();
    shape.insert(normalized, 1);
    Ok((shape, tensor.dtype, tensor.data.clone()))
}

#[derive(Clone, Copy)]
pub enum ReduceOp {
    Sum,
    Mean,
    Min,
    Max,
}

pub fn reduce(
    tensor: &TensorData,
    axis: Option<&[i64]>,
    keep_dims: bool,
    op: ReduceOp,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let rank = tensor.shape.len();
    let axes: Vec<usize> = match axis {
        None => (0..rank).collect(),
        Some(list) => {
            let mut resolved = Vec::with_capacity(list.len());
            for &value in list {
                resolved.push(normalize_axis(value, rank, false)?);
            }
            resolved
        }
    };
    let mut unique = axes.clone();
    unique.sort_unstable();
    unique.dedup();
    if unique.len() != axes.len() {
        return Err(TensorCoreError::new("TSF-005", "duplicate reduction axis"));
    }
    let out_shape: Vec<usize> = if keep_dims {
        tensor
            .shape
            .iter()
            .enumerate()
            .map(|(i, &size)| if axes.contains(&i) { 1 } else { size })
            .collect()
    } else {
        tensor
            .shape
            .iter()
            .enumerate()
            .filter(|(i, _)| !axes.contains(i))
            .map(|(_, &size)| size)
            .collect()
    };
    let mut groups: Vec<Vec<f64>> = vec![Vec::new(); product(&out_shape).max(1)];
    for (index, &item) in tensor.data.iter().enumerate() {
        let coord = coords(index, &tensor.shape);
        let out_coord: Vec<usize> = if keep_dims {
            coord
                .iter()
                .enumerate()
                .map(|(i, &c)| if axes.contains(&i) { 0 } else { c })
                .collect()
        } else {
            coord
                .iter()
                .enumerate()
                .filter(|(i, _)| !axes.contains(i))
                .map(|(_, &c)| c)
                .collect()
        };
        let flat = flat_index(&out_coord, &out_shape);
        groups[flat].push(item);
    }
    let dtype = match op {
        ReduceOp::Mean => Dtype::F64,
        _ => tensor.dtype,
    };
    let data: Vec<f64> = groups
        .into_iter()
        .map(|group| match op {
            ReduceOp::Sum => group.iter().sum(),
            ReduceOp::Mean => group.iter().sum::<f64>() / group.len() as f64,
            ReduceOp::Min => group.iter().cloned().fold(f64::INFINITY, f64::min),
            ReduceOp::Max => group.iter().cloned().fold(f64::NEG_INFINITY, f64::max),
        })
        .collect();
    Ok((out_shape, dtype, data))
}

/// Parallelizes *across* independent output groups; each group's own
/// reduction is still a strictly sequential fold over that group's
/// elements in the exact same fixed order the sequential `reduce`
/// builds it in (source flat-index order) -- only *which* groups run on
/// which thread varies, never the order elements are combined within a
/// group, so results are bit-identical to `reduce` regardless of thread
/// scheduling. A reduction to a single output group (e.g. `axis: None`
/// reducing a whole Tensor to one scalar) gets no parallelism from this
/// function -- there is nothing to split across groups when there is
/// only one -- a documented limitation of this pass, not attempted here
/// (splitting *within* one group's sum would reorder floating-point
/// summation, which is exactly what `NumericMode::CompatReference`
/// forbids and this function's callers only ever use in `NativeFast`
/// mode anyway, but doing it safely and deterministically needs a
/// fixed-topology chunked reduction this pass doesn't build).
pub fn reduce_parallel(
    tensor: &TensorData,
    axis: Option<&[i64]>,
    keep_dims: bool,
    op: ReduceOp,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let rank = tensor.shape.len();
    let axes: Vec<usize> = match axis {
        None => (0..rank).collect(),
        Some(list) => {
            let mut resolved = Vec::with_capacity(list.len());
            for &value in list {
                resolved.push(normalize_axis(value, rank, false)?);
            }
            resolved
        }
    };
    let mut unique = axes.clone();
    unique.sort_unstable();
    unique.dedup();
    if unique.len() != axes.len() {
        return Err(TensorCoreError::new("TSF-005", "duplicate reduction axis"));
    }
    let out_shape: Vec<usize> = if keep_dims {
        tensor
            .shape
            .iter()
            .enumerate()
            .map(|(i, &size)| if axes.contains(&i) { 1 } else { size })
            .collect()
    } else {
        tensor
            .shape
            .iter()
            .enumerate()
            .filter(|(i, _)| !axes.contains(i))
            .map(|(_, &size)| size)
            .collect()
    };
    let mut groups: Vec<Vec<f64>> = vec![Vec::new(); product(&out_shape).max(1)];
    for (index, &item) in tensor.data.iter().enumerate() {
        let coord = coords(index, &tensor.shape);
        let out_coord: Vec<usize> = if keep_dims {
            coord
                .iter()
                .enumerate()
                .map(|(i, &c)| if axes.contains(&i) { 0 } else { c })
                .collect()
        } else {
            coord
                .iter()
                .enumerate()
                .filter(|(i, _)| !axes.contains(i))
                .map(|(_, &c)| c)
                .collect()
        };
        let flat = flat_index(&out_coord, &out_shape);
        groups[flat].push(item);
    }
    let dtype = match op {
        ReduceOp::Mean => Dtype::F64,
        _ => tensor.dtype,
    };
    let data: Vec<f64> = groups
        .par_iter()
        .map(|group| match op {
            ReduceOp::Sum => group.iter().sum(),
            ReduceOp::Mean => group.iter().sum::<f64>() / group.len() as f64,
            ReduceOp::Min => group.iter().cloned().fold(f64::INFINITY, f64::min),
            ReduceOp::Max => group.iter().cloned().fold(f64::NEG_INFINITY, f64::max),
        })
        .collect();
    Ok((out_shape, dtype, data))
}

pub enum ArgOp {
    Max,
    Min,
}

pub fn arg_reduce(
    tensor: &TensorData,
    axis: Option<i64>,
    keep_dims: bool,
    op: ArgOp,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if axis.is_none() {
        let mut best_index = 0usize;
        for (index, &value) in tensor.data.iter().enumerate() {
            let better = match op {
                ArgOp::Max => value > tensor.data[best_index],
                ArgOp::Min => value < tensor.data[best_index],
            };
            if better {
                best_index = index;
            }
        }
        return Ok((vec![], Dtype::I64, vec![best_index as f64]));
    }
    let axis = normalize_axis(axis.unwrap(), tensor.shape.len(), false)?;
    let out_shape: Vec<usize> = if keep_dims {
        tensor
            .shape
            .iter()
            .enumerate()
            .map(|(i, &size)| if i == axis { 1 } else { size })
            .collect()
    } else {
        tensor
            .shape
            .iter()
            .enumerate()
            .filter(|(i, _)| *i != axis)
            .map(|(_, &size)| size)
            .collect()
    };
    let mut out = Vec::with_capacity(product(&out_shape));
    for out_index in 0..product(&out_shape) {
        let mut base = coords(out_index, &out_shape);
        if !keep_dims {
            base.insert(axis, 0);
        }
        let mut best_position = 0usize;
        let mut best_value = f64::NAN;
        for position in 0..tensor.shape[axis] {
            base[axis] = position;
            let flat = flat_index(&base, &tensor.shape);
            let value = tensor.data[flat];
            if position == 0
                || match op {
                    ArgOp::Max => value > best_value,
                    ArgOp::Min => value < best_value,
                }
            {
                best_value = value;
                best_position = position;
            }
        }
        out.push(best_position as f64);
    }
    Ok((out_shape, Dtype::I64, out))
}

pub fn dot(left: &TensorData, right: &TensorData) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if left.shape.len() != 1 || left.shape != right.shape {
        return Err(TensorCoreError::new(
            "TSF-008",
            "dot requires equal rank-1 Tensors",
        ));
    }
    let sum: f64 = left
        .data
        .iter()
        .zip(right.data.iter())
        .map(|(a, b)| a * b)
        .sum();
    Ok((vec![], promote(left.dtype, right.dtype), vec![sum]))
}

pub fn matmul(left: &TensorData, right: &TensorData) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if left.shape.len() != 2 || right.shape.len() != 2 {
        return Err(TensorCoreError::new(
            "TSF-004",
            "v0.1 matmul requires rank-2 Tensors",
        ));
    }
    let (m, k) = (left.shape[0], left.shape[1]);
    let (k2, n) = (right.shape[0], right.shape[1]);
    if k != k2 {
        return Err(TensorCoreError::new(
            "TSF-008",
            "matmul inner dimensions must match",
        ));
    }
    let mut data = vec![0.0; m * n];
    for row in 0..m {
        for col in 0..n {
            let mut sum = 0.0;
            for inner in 0..k {
                sum += left.data[row * k + inner] * right.data[inner * n + col];
            }
            data[row * n + col] = sum;
        }
    }
    Ok((vec![m, n], promote(left.dtype, right.dtype), data))
}

/// Parallelizes across output *rows*; each row's `k`-length inner dot
/// product is still a strictly sequential fold in the same fixed
/// `inner in 0..k` order the sequential `matmul` uses -- deterministic
/// for the same reason `reduce_parallel` is: only the row-to-thread
/// assignment varies, never the order any single row's sum is
/// accumulated in.
pub fn matmul_parallel(left: &TensorData, right: &TensorData) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if left.shape.len() != 2 || right.shape.len() != 2 {
        return Err(TensorCoreError::new(
            "TSF-004",
            "v0.1 matmul requires rank-2 Tensors",
        ));
    }
    let (m, k) = (left.shape[0], left.shape[1]);
    let (k2, n) = (right.shape[0], right.shape[1]);
    if k != k2 {
        return Err(TensorCoreError::new(
            "TSF-008",
            "matmul inner dimensions must match",
        ));
    }
    let rows: Vec<Vec<f64>> = (0..m)
        .into_par_iter()
        .map(|row| {
            let mut row_data = vec![0.0; n];
            for col in 0..n {
                let mut sum = 0.0;
                for inner in 0..k {
                    sum += left.data[row * k + inner] * right.data[inner * n + col];
                }
                row_data[col] = sum;
            }
            row_data
        })
        .collect();
    let data: Vec<f64> = rows.into_iter().flatten().collect();
    Ok((vec![m, n], promote(left.dtype, right.dtype), data))
}

pub fn norm(tensor: &TensorData, order: i64) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let result = match order {
        1 => tensor.data.iter().map(|value| value.abs()).sum(),
        2 => tensor
            .data
            .iter()
            .map(|value| value * value)
            .sum::<f64>()
            .sqrt(),
        _ => {
            return Err(TensorCoreError::new(
                "TSF-016",
                "v0.1 norm supports only orders 1 and 2",
            ))
        }
    };
    Ok((vec![], Dtype::F64, vec![result]))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tensor(shape: Vec<usize>, dtype: Dtype, data: Vec<f64>) -> TensorData {
        TensorData { shape, dtype, data }
    }

    #[test]
    fn broadcast_binary_parallel_matches_sequential() {
        let left = tensor(vec![257], Dtype::F64, (0..257).map(|v| v as f64 * 1.5).collect());
        let right = tensor(vec![257], Dtype::F64, (0..257).map(|v| v as f64 * 0.5 + 1.0).collect());
        let (shape_seq, dtype_seq, data_seq) =
            broadcast_binary(&left, &right, |a, b| a * b - a.sqrt(), None).unwrap();
        let (shape_par, dtype_par, data_par) =
            broadcast_binary_parallel(&left, &right, |a, b| a * b - a.sqrt(), None).unwrap();
        assert_eq!(shape_seq, shape_par);
        assert_eq!(dtype_seq, dtype_par);
        assert_eq!(data_seq, data_par);
    }

    #[test]
    fn unary_parallel_matches_sequential() {
        let input = tensor(vec![513], Dtype::F64, (0..513).map(|v| v as f64 * 0.01 + 0.01).collect());
        let (shape_seq, dtype_seq, data_seq) = unary(&input, f64::ln, None);
        let (shape_par, dtype_par, data_par) = unary_parallel(&input, f64::ln, None);
        assert_eq!(shape_seq, shape_par);
        assert_eq!(dtype_seq, dtype_par);
        assert_eq!(data_seq, data_par);
    }

    #[test]
    fn reduce_parallel_matches_sequential_across_multiple_groups() {
        let input = tensor(
            vec![64, 129],
            Dtype::F64,
            (0..64 * 129).map(|v| ((v * 7919) % 1013) as f64 * 0.001).collect(),
        );
        let (shape_seq, dtype_seq, data_seq) =
            reduce(&input, Some(&[1]), false, ReduceOp::Sum).unwrap();
        let (shape_par, dtype_par, data_par) =
            reduce_parallel(&input, Some(&[1]), false, ReduceOp::Sum).unwrap();
        assert_eq!(shape_seq, shape_par);
        assert_eq!(dtype_seq, dtype_par);
        assert_eq!(data_seq, data_par);
    }

    #[test]
    fn matmul_parallel_matches_sequential() {
        let left = tensor(vec![37, 41], Dtype::F64, (0..37 * 41).map(|v| (v % 17) as f64 * 0.1).collect());
        let right = tensor(vec![41, 29], Dtype::F64, (0..41 * 29).map(|v| (v % 13) as f64 * 0.2).collect());
        let (shape_seq, dtype_seq, data_seq) = matmul(&left, &right).unwrap();
        let (shape_par, dtype_par, data_par) = matmul_parallel(&left, &right).unwrap();
        assert_eq!(shape_seq, shape_par);
        assert_eq!(dtype_seq, dtype_par);
        assert_eq!(data_seq, data_par);
    }

    #[test]
    fn round_for_mode_only_rounds_f32_in_native_fast() {
        use crate::dtype::NumericMode;

        let precise = std::f64::consts::PI;
        assert_eq!(Dtype::F32.round_for_mode(precise, NumericMode::CompatReference), precise);
        assert_eq!(
            Dtype::F32.round_for_mode(precise, NumericMode::NativeFast),
            precise as f32 as f64
        );
        assert_ne!(precise as f32 as f64, precise);
        // f64 and int/bool dtypes are unaffected by the mode.
        assert_eq!(Dtype::F64.round_for_mode(precise, NumericMode::NativeFast), precise);
        assert_eq!(Dtype::I32.round_for_mode(3.7, NumericMode::NativeFast), 3.0);
    }
}
