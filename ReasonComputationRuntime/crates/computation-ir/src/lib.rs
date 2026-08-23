//! `reason-computation-ir/0.1` decoder and basic-block VM.
//!
//! See `AGENTS.md` (repository root) for how this fits into the
//! ReasonScript modernization plan's phase roadmap, and
//! `frontend/computation_ir/` for the Python side this is validated
//! against.

pub mod ir;
pub mod optimizer_dispatch;
pub mod relation_dispatch;
pub mod tensor_dispatch;
pub mod value;
pub mod vm;

pub use ir::{decode, Program, SCHEMA};
pub use reasonscript_tensor_core::NumericMode;
pub use value::{to_json, Value};
pub use vm::{RuntimeError, Vm};
