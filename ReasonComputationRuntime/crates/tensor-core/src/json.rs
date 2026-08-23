//! JSON <-> Tensor value conversion, matching `frontend/tensor/runtime.py`'s
//! `_shape_and_flat` / `_infer_dtype` / `_nested` for `tensor.create`,
//! `tensor.to_array`, and `tensor.scalar`.

use crate::dtype::Dtype;
use crate::error::{Result, TensorCoreError};
use crate::shape::product;
use crate::store::TensorData;

/// Flattens a (possibly nested) JSON array of numbers/bools into a flat
/// `Vec<f64>` plus its shape, and infers a dtype the way `create()` does
/// when no explicit dtype is given: all-bool -> bool, all-bool-or-int ->
/// i64, otherwise f64.
pub fn shape_and_flat(value: &serde_json::Value) -> Result<(Vec<usize>, Vec<f64>, Dtype)> {
    let (shape, flat, all_bool, all_int) = walk(value)?;
    let dtype = if all_bool {
        Dtype::Bool
    } else if all_int {
        Dtype::I64
    } else {
        Dtype::F64
    };
    Ok((shape, flat, dtype))
}

fn walk(value: &serde_json::Value) -> Result<(Vec<usize>, Vec<f64>, bool, bool)> {
    match value {
        serde_json::Value::Bool(v) => Ok((vec![], vec![if *v { 1.0 } else { 0.0 }], true, true)),
        serde_json::Value::Number(v) => {
            let is_int = v.is_i64() || v.is_u64();
            let raw = v.as_f64().ok_or_else(|| {
                TensorCoreError::new(
                    "TSF-016",
                    "Tensor data must be numeric, boolean, or an array",
                )
            })?;
            Ok((vec![], vec![raw], false, is_int))
        }
        serde_json::Value::Array(items) => {
            if items.is_empty() {
                return Ok((vec![0], vec![], true, true));
            }
            let mut child_shape: Option<Vec<usize>> = None;
            let mut flat = Vec::new();
            let mut all_bool = true;
            let mut all_int = true;
            for item in items {
                let (shape, values, is_bool, is_int) = walk(item)?;
                match &child_shape {
                    None => child_shape = Some(shape),
                    Some(expected) if *expected != shape => {
                        return Err(TensorCoreError::new(
                            "TSF-017",
                            "Tensor input array must be rectangular",
                        ))
                    }
                    _ => {}
                }
                all_bool &= is_bool;
                all_int &= is_int;
                flat.extend(values);
            }
            let mut shape = vec![items.len()];
            shape.extend(child_shape.unwrap_or_default());
            Ok((shape, flat, all_bool, all_int))
        }
        _ => Err(TensorCoreError::new(
            "TSF-016",
            "Tensor data must be numeric, boolean, or an array",
        )),
    }
}

fn leaf_json(dtype: Dtype, raw: f64) -> serde_json::Value {
    match dtype {
        Dtype::Bool => serde_json::Value::Bool(raw != 0.0),
        Dtype::I32 | Dtype::I64 => serde_json::json!(raw as i64),
        Dtype::F32 | Dtype::F64 => serde_json::json!(raw),
    }
}

/// Reconstructs a nested JSON array from flat data + shape, matching
/// `_nested`, for `tensor.to_array`.
pub fn nested_json(tensor: &TensorData) -> serde_json::Value {
    build_nested(tensor.dtype, &tensor.data, &tensor.shape)
}

fn build_nested(dtype: Dtype, data: &[f64], shape: &[usize]) -> serde_json::Value {
    if shape.is_empty() {
        return leaf_json(dtype, data[0]);
    }
    let step = product(&shape[1..]).max(1);
    let items: Vec<serde_json::Value> = data
        .chunks(step)
        .map(|chunk| build_nested(dtype, chunk, &shape[1..]))
        .collect();
    serde_json::Value::Array(items)
}

/// `tensor.scalar`: requires exactly one element.
pub fn scalar_json(tensor: &TensorData) -> Result<serde_json::Value> {
    if tensor.data.len() != 1 {
        return Err(TensorCoreError::new(
            "TSF-011",
            "Tensor cannot be converted to Scalar",
        ));
    }
    Ok(leaf_json(tensor.dtype, tensor.data[0]))
}
