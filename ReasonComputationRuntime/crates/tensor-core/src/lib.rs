//! Phase 4 "Rust Tensor forward": storage/handle, dense CPU reference
//! ops, `.rstensor` I/O, and RNG, matching
//! `frontend/tensor/runtime.py`'s `PythonTensorBackend` for the
//! functions this crate implements. See `AGENTS.md` (repository root)
//! for the exact function list and what's deferred to later work.
//!
//! Everything here computes in `f64` regardless of declared dtype (the
//! plan's "compat-reference" numeric mode, section 10) -- true `f32`
//! computation is `native-fast` (Phase 9) scope.

pub mod autograd;
pub mod dtype;
pub mod error;
pub mod io;
pub mod json;
pub mod ops;
pub mod rng;
pub mod shape;
pub mod store;

pub use autograd::{Autograd, GradOp};
pub use dtype::{Dtype, NumericMode};
pub use error::{Result, TensorCoreError};
pub use store::{TensorData, TensorStore};
