//! Tensor storage and handle registry, matching
//! `frontend/tensor/runtime.py`'s `_Tensor` / `TensorRuntime._new` /
//! `TensorRuntime._refs`.
//!
//! Simplification vs. the Python side (documented, not a silent gap):
//! resource-policy limits (`max_live_tensors`, `max_elements`,
//! `max_tensor_bytes`, `max_rank`, ...) are not enforced here yet, and
//! non-finite values are rejected with a single `TSF-010` regardless of
//! which operation produced them (Python distinguishes `TSF-010` at
//! creation from `TSF-012` mid-computation). Shape/rank/finite-value
//! *correctness* is enforced; the resource *policy* ceiling is Phase 4
//! follow-up scope.

use std::collections::HashMap;

use crate::autograd::{Autograd, GradOp};
use crate::dtype::{Dtype, NumericMode};
use crate::error::{Result, TensorCoreError};
use crate::shape::product;

#[derive(Clone, Debug)]
pub struct TensorData {
    pub shape: Vec<usize>,
    pub dtype: Dtype,
    pub data: Vec<f64>,
}

pub struct TensorStore {
    refs: HashMap<String, TensorData>,
    next_id: u64,
    pub autograd: Autograd,
    numeric_mode: NumericMode,
}

impl Default for TensorStore {
    fn default() -> Self {
        Self::new()
    }
}

impl TensorStore {
    pub fn new() -> Self {
        TensorStore {
            refs: HashMap::new(),
            next_id: 1,
            autograd: Autograd::default(),
            numeric_mode: NumericMode::default(),
        }
    }

    pub fn with_numeric_mode(mode: NumericMode) -> Self {
        TensorStore {
            numeric_mode: mode,
            ..Self::new()
        }
    }

    pub fn numeric_mode(&self) -> NumericMode {
        self.numeric_mode
    }

    pub fn get(&self, id: &str) -> Result<&TensorData> {
        self.refs
            .get(id)
            .ok_or_else(|| TensorCoreError::new("TSF-001", format!("unknown Tensor handle: {id}")))
    }

    /// Validates shape/dtype/finiteness and stores a fresh Tensor,
    /// returning its handle id (`tensor_%04d`, matching the Python side's
    /// counter format).
    pub fn insert(&mut self, shape: Vec<usize>, dtype: Dtype, data: Vec<f64>) -> Result<String> {
        validate_shape(&shape)?;
        if data.len() != product(&shape) {
            return Err(TensorCoreError::new(
                "TSF-009",
                "Tensor element count does not match shape",
            ));
        }
        let casted: Vec<f64> = data
            .iter()
            .map(|value| dtype.round_for_mode(*value, self.numeric_mode))
            .collect();
        validate_finite(&casted)?;
        let id = format!("tensor_{:04}", self.next_id);
        self.next_id += 1;
        self.refs.insert(
            id.clone(),
            TensorData {
                shape,
                dtype,
                data: casted,
            },
        );
        Ok(id)
    }

    /// `insert`, then tapes `op` if at least one of its inputs is
    /// grad-tracked (mirroring `_record_autograd`) -- only meaningful for
    /// f32/f64 outputs, like the Python side (a bool/int-dtype result
    /// can't carry a gradient).
    pub fn insert_with_grad(
        &mut self,
        shape: Vec<usize>,
        dtype: Dtype,
        data: Vec<f64>,
        op: GradOp,
    ) -> Result<String> {
        let id = self.insert(shape, dtype, data)?;
        if matches!(dtype, Dtype::F32 | Dtype::F64) {
            self.autograd.record(&id, op);
        }
        Ok(id)
    }
}

fn validate_shape(shape: &[usize]) -> Result<()> {
    if shape.is_empty() {
        return Ok(()); // rank-0 scalar Tensor
    }
    if shape.iter().any(|&dimension| dimension == 0) {
        return Err(TensorCoreError::new(
            "TSF-009",
            "Empty tensor is not allowed",
        ));
    }
    Ok(())
}

fn validate_finite(data: &[f64]) -> Result<()> {
    for (index, value) in data.iter().enumerate() {
        if value.is_nan() || value.is_infinite() {
            return Err(TensorCoreError::new(
                "TSF-010",
                format!("Tensor contains a non-finite value at flattened index {index}"),
            ));
        }
    }
    Ok(())
}
