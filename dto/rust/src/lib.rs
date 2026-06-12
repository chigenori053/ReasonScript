//! Rust binding for the ReasonScript Common DTO v0.1 contract.
//!
//! The reference Runtime owns the canonical Rust DTO definitions. This crate
//! exposes only public wire DTOs.

pub use reasonscript_hybrid_runtime::{
    ConstraintSpec, ContextRef, ExecutionPlan, ExecutionPolicy, GoalSpec, InferenceResult,
    InferenceStatus, PlanPath, PlanStep, PlannerPolicy, Proof, ReasonIR, StateDelta, StateSnapshot,
    Trace, TraceEvent, TracePolicy, TransactionRecord, TransactionStatus, TransitionSpec,
    Violation, REASON_IR_SCHEMA_ID, REASON_IR_VERSION,
};
