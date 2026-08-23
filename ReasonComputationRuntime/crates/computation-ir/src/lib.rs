//! `reason-computation-ir/0.1` decoder and Phase 3 Tensor-less VM.
//!
//! See `AGENTS.md` (repository root) for how this fits into the
//! ReasonScript modernization plan's phase roadmap, and
//! `frontend/computation_ir/` for the Python side this is validated
//! against.

pub mod ir;
pub mod value;
pub mod vm;

pub use ir::{decode, Program, SCHEMA};
pub use value::{to_json, Value};
pub use vm::{RuntimeError, Vm};
