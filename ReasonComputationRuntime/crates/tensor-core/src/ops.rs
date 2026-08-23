//! Dense CPU reference Tensor operations, matching
//! `frontend/tensor/runtime.py`'s `PythonTensorBackend` methods
//! elementwise, shape-op-for-shape-op, and reduction-for-reduction.

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
