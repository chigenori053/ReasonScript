//! Tensor storage and handle registry, matching
//! `frontend/tensor/runtime.py`'s `_Tensor` / `TensorRuntime._new` /
//! `TensorRuntime._refs`.
//!
//! Resource-policy limits, Tensor I/O capabilities, and resource-root path
//! confinement are enforced here. One remaining diagnostic simplification is
//! that non-finite values are rejected with a single `TSF-010` regardless of
//! which operation produced them (Python distinguishes `TSF-010` at
//! creation from `TSF-012` mid-computation). Shape/rank/finite-value
//! *correctness* is enforced.

use std::collections::HashMap;
use std::path::{Component, Path, PathBuf};

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
    policy: TensorPolicy,
    resource_root: PathBuf,
    filesystem_read: bool,
    filesystem_write: bool,
}

#[derive(Clone, Debug)]
pub struct TensorPolicy {
    pub max_rank: usize,
    pub max_elements: usize,
    pub max_tensor_bytes: usize,
    pub max_live_tensors: usize,
    pub max_shape_dimension: usize,
    pub max_artifact_bytes: usize,
    pub inline_elements: usize,
    pub max_autograd_nodes: usize,
    pub max_saved_tensor_bytes: usize,
}

impl Default for TensorPolicy {
    fn default() -> Self {
        Self {
            max_rank: 8,
            max_elements: 10_000_000,
            max_tensor_bytes: 256 * 1024 * 1024,
            max_live_tensors: 1_000,
            max_shape_dimension: 10_000_000,
            max_artifact_bytes: 256 * 1024 * 1024,
            inline_elements: 256,
            max_autograd_nodes: 100_000,
            max_saved_tensor_bytes: 512 * 1024 * 1024,
        }
    }
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
            policy: TensorPolicy::default(),
            resource_root: std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            filesystem_read: true,
            filesystem_write: true,
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

    pub fn configure_context(
        &mut self,
        policy: TensorPolicy,
        resource_root: PathBuf,
        filesystem_read: bool,
        filesystem_write: bool,
    ) {
        self.policy = policy;
        self.resource_root = resource_root;
        self.filesystem_read = filesystem_read;
        self.filesystem_write = filesystem_write;
    }

    pub fn metadata(&self) -> Vec<serde_json::Value> {
        let mut ids: Vec<_> = self.refs.keys().collect();
        ids.sort();
        ids.into_iter()
            .map(|id| {
                let tensor = &self.refs[id];
                serde_json::json!({
                    "tensor_id": id,
                    "shape": tensor.shape,
                    "rank": tensor.shape.len(),
                    "dtype": tensor.dtype.name(),
                    "device": "cpu",
                    "backend": "rust",
                    "storage_ref": format!("runtime://tensor/{id}"),
                    "lifecycle": "available",
                })
            })
            .collect()
    }

    pub fn tensor_info(&self, id: &str) -> Option<serde_json::Value> {
        self.refs.get(id).map(|tensor| {
            serde_json::json!({
                "tensor_id": id,
                "shape": tensor.shape,
                "dtype": tensor.dtype.name(),
                "device": "cpu",
                "backend": "rust",
            })
        })
    }

    pub fn collect(&mut self, roots: &std::collections::HashSet<String>) -> usize {
        let mut reachable = self.autograd.live_tensor_ids();
        reachable.extend(roots.iter().cloned());
        let before = self.refs.len();
        self.refs.retain(|id, _| reachable.contains(id));
        before - self.refs.len()
    }

    pub fn resolve_io_path(&self, raw: &str, write: bool) -> Result<PathBuf> {
        if write && !self.filesystem_write {
            return Err(TensorCoreError::new(
                "TIO-001",
                "tensor.save requires filesystem_write capability",
            ));
        }
        if !write && !self.filesystem_read {
            return Err(TensorCoreError::new(
                "TIO-001",
                "tensor.load requires filesystem_read capability",
            ));
        }
        if raw.is_empty() || raw.contains('\\') {
            return Err(TensorCoreError::new("TIO-002", "unsafe Tensor path"));
        }
        let path = Path::new(raw);
        if path.is_absolute()
            || path.components().any(|part| {
                matches!(
                    part,
                    Component::ParentDir
                        | Component::CurDir
                        | Component::RootDir
                        | Component::Prefix(_)
                )
            })
        {
            return Err(TensorCoreError::new("TIO-002", "unsafe Tensor path"));
        }
        if path.extension().and_then(|value| value.to_str()) != Some("rstensor") {
            return Err(TensorCoreError::new(
                "TIO-002",
                "Tensor path must use .rstensor",
            ));
        }
        Ok(self.resource_root.join(path))
    }

    pub fn check_artifact_size(&self, size: usize) -> Result<()> {
        if size > self.policy.max_artifact_bytes {
            Err(TensorCoreError::new(
                "TIO-003",
                "Tensor file exceeds resource policy",
            ))
        } else {
            Ok(())
        }
    }

    pub fn check_inline_size(&self, size: usize) -> Result<()> {
        if size > self.policy.inline_elements {
            Err(TensorCoreError::new(
                "TSF-020",
                "Tensor exceeds to_array policy",
            ))
        } else {
            Ok(())
        }
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
        if self.refs.len() >= self.policy.max_live_tensors {
            return Err(TensorCoreError::new(
                "TSF-013",
                "maximum live Tensor count exceeded",
            ));
        }
        validate_shape(&shape, dtype, &self.policy)?;
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
        let should_record =
            matches!(dtype, Dtype::F32 | Dtype::F64) && self.autograd.would_record(&op);
        if should_record && self.autograd.node_count() >= self.policy.max_autograd_nodes {
            return Err(TensorCoreError::new(
                "AD-005",
                "maximum autograd node count exceeded",
            ));
        }
        if should_record {
            let saved_bytes: usize = self
                .autograd
                .live_tensor_ids()
                .iter()
                .filter_map(|id| self.refs.get(id))
                .map(|tensor| tensor.data.len().saturating_mul(tensor.dtype.byte_width()))
                .sum::<usize>()
                .saturating_add(data.len().saturating_mul(dtype.byte_width()));
            if saved_bytes > self.policy.max_saved_tensor_bytes {
                return Err(TensorCoreError::new(
                    "AD-005",
                    "autograd saved Tensor policy exceeded",
                ));
            }
        }
        let id = self.insert(shape, dtype, data)?;
        if should_record {
            self.autograd.record(&id, op);
        }
        Ok(id)
    }
}

fn validate_shape(shape: &[usize], dtype: Dtype, policy: &TensorPolicy) -> Result<()> {
    if shape.is_empty() {
        return Ok(()); // rank-0 scalar Tensor
    }
    if shape.iter().any(|&dimension| dimension == 0) {
        return Err(TensorCoreError::new(
            "TSF-009",
            "Empty tensor is not allowed",
        ));
    }
    if shape.len() > policy.max_rank
        || shape
            .iter()
            .any(|dimension| *dimension > policy.max_shape_dimension)
    {
        return Err(TensorCoreError::new("TSF-003", "invalid Tensor shape"));
    }
    let size = product(shape);
    if size > policy.max_elements
        || size.saturating_mul(dtype.byte_width()) > policy.max_tensor_bytes
    {
        return Err(TensorCoreError::new(
            "TSF-003",
            "Tensor shape exceeds resource policy",
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
