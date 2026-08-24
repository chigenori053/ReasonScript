//! Shape/coordinate math, matching `frontend/tensor/runtime.py`'s
//! `_product`/`_strides`/`_coords`/`_flat_index`/`_broadcast_shape`/
//! `_broadcast_value`/`_normalize_axis` exactly (same numpy-style
//! right-aligned broadcasting rules, same row-major strides).

use crate::error::{Result, TensorCoreError};

pub fn product(shape: &[usize]) -> usize {
    shape.iter().product()
}

pub fn strides(shape: &[usize]) -> Vec<usize> {
    (0..shape.len())
        .map(|index| product(&shape[index + 1..]))
        .collect()
}

pub fn coords(index: usize, shape: &[usize]) -> Vec<usize> {
    let strides = strides(shape);
    let mut result = Vec::with_capacity(shape.len());
    for (stride, dimension) in strides.iter().zip(shape.iter()) {
        if *dimension == 0 {
            result.push(0);
            continue;
        }
        result.push((index / stride) % dimension);
    }
    result
}

pub fn flat_index(coords: &[usize], shape: &[usize]) -> usize {
    let strides = strides(shape);
    coords
        .iter()
        .zip(strides.iter())
        .map(|(coord, stride)| coord * stride)
        .sum()
}

pub fn broadcast_shape(left: &[usize], right: &[usize]) -> Result<Vec<usize>> {
    let mut result = Vec::with_capacity(left.len().max(right.len()));
    for (a, b) in left.iter().rev().zip(right.iter().rev()) {
        if a != b && *a != 1 && *b != 1 {
            return Err(TensorCoreError::new(
                "TSF-006",
                "Tensor shapes cannot be broadcast",
            ));
        }
        result.push(*a.max(b));
    }
    let longer = if left.len() > right.len() {
        left
    } else {
        right
    };
    let extra = longer.len().abs_diff(left.len().min(right.len()));
    for value in longer[..extra].iter().rev() {
        result.push(*value);
    }
    result.reverse();
    Ok(result)
}

/// Reads the value at `out_coords` from a Tensor of `shape`, broadcasting
/// size-1 dimensions, matching `_broadcast_value`.
pub fn broadcast_flat_index(out_coords: &[usize], shape: &[usize]) -> usize {
    let offset = out_coords.len() - shape.len();
    let source_coords: Vec<usize> = shape
        .iter()
        .enumerate()
        .map(|(i, size)| {
            if *size == 1 {
                0
            } else {
                out_coords[offset + i]
            }
        })
        .collect();
    flat_index(&source_coords, shape)
}

pub fn normalize_axis(axis: i64, rank: usize, insertion: bool) -> Result<usize> {
    let limit = if insertion {
        rank as i64 + 1
    } else {
        rank as i64
    };
    let normalized = if axis < 0 { axis + limit } else { axis };
    if normalized < 0 || normalized >= limit {
        return Err(TensorCoreError::new(
            "TSF-005",
            format!("axis is out of range: axis={axis}, rank={rank}"),
        ));
    }
    Ok(normalized as usize)
}

pub fn all_coords(shape: &[usize]) -> Vec<Vec<usize>> {
    if shape.is_empty() {
        return vec![vec![]];
    }
    let mut result = vec![vec![]];
    for &size in shape {
        let mut next = Vec::with_capacity(result.len() * size.max(1));
        for prefix in &result {
            for value in 0..size {
                let mut extended = prefix.clone();
                extended.push(value);
                next.push(extended);
            }
        }
        result = next;
    }
    result
}
