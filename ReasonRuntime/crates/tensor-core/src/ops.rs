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

pub fn concat(tensors: &[TensorData], axis: i64) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let first = tensors
        .first()
        .ok_or_else(|| TensorCoreError::new("TSF-009", "concat requires at least one Tensor"))?;
    let rank = first.shape.len();
    let axis = normalize_axis(axis, rank, false)?;
    if tensors.iter().any(|tensor| {
        tensor.shape.len() != rank
            || tensor
                .shape
                .iter()
                .enumerate()
                .any(|(index, size)| index != axis && *size != first.shape[index])
    }) {
        return Err(TensorCoreError::new(
            "TSF-009",
            "concat shapes do not match",
        ));
    }
    let mut shape = first.shape.clone();
    shape[axis] = tensors.iter().map(|tensor| tensor.shape[axis]).sum();
    let mut data = vec![0.0; product(&shape)];
    let mut offset = 0;
    for tensor in tensors {
        for (index, item) in tensor.data.iter().enumerate() {
            let mut coordinate = coords(index, &tensor.shape);
            coordinate[axis] += offset;
            data[flat_index(&coordinate, &shape)] = *item;
        }
        offset += tensor.shape[axis];
    }
    Ok((shape, first.dtype, data))
}

pub fn stack(tensors: &[TensorData], axis: i64) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let first = tensors
        .first()
        .ok_or_else(|| TensorCoreError::new("TSF-010", "stack requires identical shapes"))?;
    if tensors.iter().any(|tensor| tensor.shape != first.shape) {
        return Err(TensorCoreError::new(
            "TSF-010",
            "stack requires identical shapes",
        ));
    }
    let normalized = normalize_axis(axis, first.shape.len(), true)?;
    let mut shape = first.shape.clone();
    shape.insert(normalized, tensors.len());
    let mut data = vec![0.0; product(&shape)];
    for (position, tensor) in tensors.iter().enumerate() {
        for (index, item) in tensor.data.iter().enumerate() {
            let coordinate = coords(index, &tensor.shape);
            let mut output = coordinate[..normalized].to_vec();
            output.push(position);
            output.extend_from_slice(&coordinate[normalized..]);
            data[flat_index(&output, &shape)] = *item;
        }
    }
    Ok((shape, first.dtype, data))
}

fn positive_slice_indexes(start: i64, end: i64, step: i64, size: usize) -> Vec<usize> {
    let size = size as i64;
    let mut begin = if start < 0 {
        (start + size).max(0)
    } else {
        start.min(size)
    };
    let stop = if end < 0 {
        (end + size).max(0)
    } else {
        end.min(size)
    };
    let mut indexes = Vec::new();
    while begin < stop {
        indexes.push(begin as usize);
        begin += step;
    }
    indexes
}

pub fn slice(
    tensor: &TensorData,
    starts: &[i64],
    ends: &[i64],
    axes: Option<&[i64]>,
    steps: Option<&[i64]>,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if starts.len() != ends.len() {
        return Err(TensorCoreError::new(
            "TSF-021",
            "slice starts and ends must have equal length",
        ));
    }
    let selected_axes: Vec<i64> = axes
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| (0..starts.len() as i64).collect());
    let selected_steps: Vec<i64> = steps
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| vec![1; starts.len()]);
    if selected_axes.len() != starts.len()
        || selected_steps.len() != starts.len()
        || selected_steps.iter().any(|step| *step <= 0)
    {
        return Err(TensorCoreError::new(
            "TSF-021",
            "invalid slice axes or steps",
        ));
    }
    let mut ranges: Vec<Vec<usize>> = tensor
        .shape
        .iter()
        .map(|size| (0..*size).collect())
        .collect();
    let mut normalized_axes = std::collections::HashSet::new();
    for (((start, end), axis), step) in starts
        .iter()
        .zip(ends)
        .zip(&selected_axes)
        .zip(&selected_steps)
    {
        let normalized = normalize_axis(*axis, tensor.shape.len(), false)?;
        if !normalized_axes.insert(normalized) {
            return Err(TensorCoreError::new("TSF-021", "duplicate slice axis"));
        }
        ranges[normalized] = positive_slice_indexes(*start, *end, *step, tensor.shape[normalized]);
    }
    let shape: Vec<usize> = ranges.iter().map(Vec::len).collect();
    if shape.contains(&0) {
        return Err(TensorCoreError::new(
            "TSF-009",
            "Empty tensor is not allowed",
        ));
    }
    let data = coordinate_product(&ranges)
        .into_iter()
        .map(|coordinate| tensor.data[flat_index(&coordinate, &tensor.shape)])
        .collect();
    Ok((shape, tensor.dtype, data))
}

fn coordinate_product(ranges: &[Vec<usize>]) -> Vec<Vec<usize>> {
    let mut result = vec![Vec::new()];
    for range in ranges {
        let mut next = Vec::with_capacity(result.len() * range.len());
        for prefix in &result {
            for value in range {
                let mut coordinate = prefix.clone();
                coordinate.push(*value);
                next.push(coordinate);
            }
        }
        result = next;
    }
    result
}

pub fn gather(
    tensor: &TensorData,
    indices: &TensorData,
    axis: i64,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if !matches!(indices.dtype, Dtype::I32 | Dtype::I64) {
        return Err(TensorCoreError::new(
            "TSF-023",
            "gather indices must use i32 or i64",
        ));
    }
    let axis = normalize_axis(axis, tensor.shape.len(), false)?;
    let mut normalized_indices = Vec::with_capacity(indices.data.len());
    for raw in &indices.data {
        let mut index = *raw as i64;
        if index < 0 {
            index += tensor.shape[axis] as i64;
        }
        if index < 0 || index >= tensor.shape[axis] as i64 {
            return Err(TensorCoreError::new(
                "TSF-022",
                "gather index is out of range",
            ));
        }
        normalized_indices.push(index as usize);
    }
    let mut shape = tensor.shape[..axis].to_vec();
    shape.extend_from_slice(&indices.shape);
    shape.extend_from_slice(&tensor.shape[axis + 1..]);
    let mut data = Vec::with_capacity(product(&shape));
    for output in all_coords(&shape) {
        let before = &output[..axis];
        let index_coordinate = &output[axis..axis + indices.shape.len()];
        let after = &output[axis + indices.shape.len()..];
        let selected = normalized_indices[flat_index(index_coordinate, &indices.shape)];
        let mut source = before.to_vec();
        source.push(selected);
        source.extend_from_slice(after);
        data.push(tensor.data[flat_index(&source, &tensor.shape)]);
    }
    Ok((shape, tensor.dtype, data))
}

pub fn softmax(tensor: &TensorData, axis: i64) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let axis = normalize_axis(axis, tensor.shape.len(), false)?;
    let mut data = vec![0.0; tensor.data.len()];
    let mut groups: std::collections::HashMap<Vec<usize>, Vec<usize>> =
        std::collections::HashMap::new();
    for index in 0..tensor.data.len() {
        let coordinate = coords(index, &tensor.shape);
        let mut key = coordinate[..axis].to_vec();
        key.extend_from_slice(&coordinate[axis + 1..]);
        groups.entry(key).or_default().push(index);
    }
    for indexes in groups.values() {
        let maximum = indexes
            .iter()
            .map(|index| tensor.data[*index])
            .fold(f64::NEG_INFINITY, f64::max);
        let denominator: f64 = indexes
            .iter()
            .map(|index| (tensor.data[*index] - maximum).exp())
            .sum();
        for index in indexes {
            data[*index] = (tensor.data[*index] - maximum).exp() / denominator;
        }
    }
    Ok((tensor.shape.clone(), tensor.dtype, data))
}

pub fn linear(
    value: &TensorData,
    weight: &TensorData,
    bias: Option<&TensorData>,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    let (shape, dtype, data) = matmul(value, weight)?;
    match bias {
        None => Ok((shape, dtype, data)),
        Some(bias) => broadcast_binary(
            &TensorData { shape, dtype, data },
            bias,
            |left, right| left + right,
            None,
        ),
    }
}

fn positive_pair(values: &[i64], label: &str, code: &str) -> Result<(usize, usize)> {
    if values.len() != 2 || values.iter().any(|value| *value <= 0) {
        return Err(TensorCoreError::new(code, format!("invalid {label}")));
    }
    Ok((values[0] as usize, values[1] as usize))
}

fn nonnegative_pair(values: &[i64], label: &str, code: &str) -> Result<(usize, usize)> {
    if values.len() != 2 || values.iter().any(|value| *value < 0) {
        return Err(TensorCoreError::new(code, format!("invalid {label}")));
    }
    Ok((values[0] as usize, values[1] as usize))
}

pub fn conv2d(
    source: &TensorData,
    kernel: &TensorData,
    bias: Option<&TensorData>,
    stride: &[i64],
    padding: &[i64],
    dilation: &[i64],
    groups: i64,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if source.shape.len() != 4 || kernel.shape.len() != 4 {
        return Err(TensorCoreError::new(
            "TSF-024",
            "conv2d requires NCHW input and OIHW weight",
        ));
    }
    let (stride_h, stride_w) = positive_pair(stride, "conv2d stride", "TSF-024")?;
    let (dilation_h, dilation_w) = positive_pair(dilation, "conv2d dilation", "TSF-024")?;
    let (pad_h, pad_w) = nonnegative_pair(padding, "conv2d padding", "TSF-024")?;
    let (batch, in_channels, in_h, in_w) = (
        source.shape[0],
        source.shape[1],
        source.shape[2],
        source.shape[3],
    );
    let (out_channels, kernel_channels, kernel_h, kernel_w) = (
        kernel.shape[0],
        kernel.shape[1],
        kernel.shape[2],
        kernel.shape[3],
    );
    if groups <= 0
        || in_channels % groups as usize != 0
        || out_channels % groups as usize != 0
        || kernel_channels != in_channels / groups as usize
    {
        return Err(TensorCoreError::new(
            "TSF-024",
            "invalid conv2d groups or channel dimensions",
        ));
    }
    let effective_h = dilation_h * (kernel_h - 1) + 1;
    let effective_w = dilation_w * (kernel_w - 1) + 1;
    if in_h + 2 * pad_h < effective_h || in_w + 2 * pad_w < effective_w {
        return Err(TensorCoreError::new(
            "TSF-024",
            "conv2d output shape is empty",
        ));
    }
    let out_h = (in_h + 2 * pad_h - effective_h) / stride_h + 1;
    let out_w = (in_w + 2 * pad_w - effective_w) / stride_w + 1;
    if let Some(bias) = bias {
        if bias.shape != vec![out_channels] {
            return Err(TensorCoreError::new(
                "TSF-024",
                "conv2d bias must have shape [out_channels]",
            ));
        }
    }
    let dtype = promote(source.dtype, kernel.dtype);
    if !matches!(dtype, Dtype::F32 | Dtype::F64) {
        return Err(TensorCoreError::new(
            "TSF-024",
            "conv2d requires floating-point Tensor values",
        ));
    }
    let channels_per_group = out_channels / groups as usize;
    let mut data = Vec::with_capacity(batch * out_channels * out_h * out_w);
    for n in 0..batch {
        for out_channel in 0..out_channels {
            let group = out_channel / channels_per_group;
            for out_y in 0..out_h {
                for out_x in 0..out_w {
                    let mut total = bias.map_or(0.0, |value| value.data[out_channel]);
                    for local_channel in 0..kernel_channels {
                        let in_channel = group * kernel_channels + local_channel;
                        for kernel_y in 0..kernel_h {
                            let input_y = out_y as i64 * stride_h as i64 - pad_h as i64
                                + kernel_y as i64 * dilation_h as i64;
                            if input_y < 0 || input_y >= in_h as i64 {
                                continue;
                            }
                            for kernel_x in 0..kernel_w {
                                let input_x = out_x as i64 * stride_w as i64 - pad_w as i64
                                    + kernel_x as i64 * dilation_w as i64;
                                if input_x < 0 || input_x >= in_w as i64 {
                                    continue;
                                }
                                total += source.data[flat_index(
                                    &[n, in_channel, input_y as usize, input_x as usize],
                                    &source.shape,
                                )] * kernel.data[flat_index(
                                    &[out_channel, local_channel, kernel_y, kernel_x],
                                    &kernel.shape,
                                )];
                            }
                        }
                    }
                    data.push(total);
                }
            }
        }
    }
    Ok((vec![batch, out_channels, out_h, out_w], dtype, data))
}

pub fn pool2d(
    source: &TensorData,
    kernel: &[i64],
    stride: Option<&[i64]>,
    padding: &[i64],
    maximum: bool,
    count_include_pad: bool,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
    if source.shape.len() != 4 || !matches!(source.dtype, Dtype::F32 | Dtype::F64) {
        return Err(TensorCoreError::new(
            "TSF-025",
            "pool2d requires floating-point NCHW input",
        ));
    }
    let (kernel_h, kernel_w) = positive_pair(kernel, "pool2d kernel", "TSF-025")?;
    let (stride_h, stride_w) = positive_pair(stride.unwrap_or(kernel), "pool2d stride", "TSF-025")?;
    let (pad_h, pad_w) = nonnegative_pair(padding, "pool2d padding", "TSF-025")?;
    let (batch, channels, in_h, in_w) = (
        source.shape[0],
        source.shape[1],
        source.shape[2],
        source.shape[3],
    );
    if in_h + 2 * pad_h < kernel_h || in_w + 2 * pad_w < kernel_w {
        return Err(TensorCoreError::new(
            "TSF-025",
            "pool2d output shape is empty",
        ));
    }
    let out_h = (in_h + 2 * pad_h - kernel_h) / stride_h + 1;
    let out_w = (in_w + 2 * pad_w - kernel_w) / stride_w + 1;
    let mut data = Vec::with_capacity(batch * channels * out_h * out_w);
    for n in 0..batch {
        for channel in 0..channels {
            for out_y in 0..out_h {
                for out_x in 0..out_w {
                    let mut values = Vec::new();
                    for kernel_y in 0..kernel_h {
                        let input_y =
                            out_y as i64 * stride_h as i64 - pad_h as i64 + kernel_y as i64;
                        for kernel_x in 0..kernel_w {
                            let input_x =
                                out_x as i64 * stride_w as i64 - pad_w as i64 + kernel_x as i64;
                            if input_y >= 0
                                && input_y < in_h as i64
                                && input_x >= 0
                                && input_x < in_w as i64
                            {
                                values.push(
                                    source.data[flat_index(
                                        &[n, channel, input_y as usize, input_x as usize],
                                        &source.shape,
                                    )],
                                );
                            } else if !maximum && count_include_pad {
                                values.push(0.0);
                            }
                        }
                    }
                    if values.is_empty() {
                        return Err(TensorCoreError::new(
                            "TSF-025",
                            "pool2d window has no values",
                        ));
                    }
                    data.push(if maximum {
                        values.into_iter().fold(f64::NEG_INFINITY, f64::max)
                    } else {
                        values.iter().sum::<f64>() / values.len() as f64
                    });
                }
            }
        }
    }
    Ok((vec![batch, channels, out_h, out_w], source.dtype, data))
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
pub fn matmul_parallel(
    left: &TensorData,
    right: &TensorData,
) -> Result<(Vec<usize>, Dtype, Vec<f64>)> {
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
            for (col, output) in row_data.iter_mut().enumerate() {
                let mut sum = 0.0;
                for inner in 0..k {
                    sum += left.data[row * k + inner] * right.data[inner * n + col];
                }
                *output = sum;
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
        let left = tensor(
            vec![257],
            Dtype::F64,
            (0..257).map(|v| v as f64 * 1.5).collect(),
        );
        let right = tensor(
            vec![257],
            Dtype::F64,
            (0..257).map(|v| v as f64 * 0.5 + 1.0).collect(),
        );
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
        let input = tensor(
            vec![513],
            Dtype::F64,
            (0..513).map(|v| v as f64 * 0.01 + 0.01).collect(),
        );
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
            (0..64 * 129)
                .map(|v| ((v * 7919) % 1013) as f64 * 0.001)
                .collect(),
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
        let left = tensor(
            vec![37, 41],
            Dtype::F64,
            (0..37 * 41).map(|v| (v % 17) as f64 * 0.1).collect(),
        );
        let right = tensor(
            vec![41, 29],
            Dtype::F64,
            (0..41 * 29).map(|v| (v % 13) as f64 * 0.2).collect(),
        );
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
        assert_eq!(
            Dtype::F32.round_for_mode(precise, NumericMode::CompatReference),
            precise
        );
        assert_eq!(
            Dtype::F32.round_for_mode(precise, NumericMode::NativeFast),
            precise as f32 as f64
        );
        assert_ne!(precise as f32 as f64, precise);
        // f64 and int/bool dtypes are unaffected by the mode.
        assert_eq!(
            Dtype::F64.round_for_mode(precise, NumericMode::NativeFast),
            precise
        );
        assert_eq!(Dtype::I32.round_for_mode(3.7, NumericMode::NativeFast), 3.0);
    }
}
