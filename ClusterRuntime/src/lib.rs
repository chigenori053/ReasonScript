//! ReasonScript Cluster Reasoning Runtime Extension v0.1.
//!
//! This crate is optional and consumes existing Reason IR / ExecutionPlan
//! artifacts without changing parser or single-node runtime semantics.

pub mod artifacts;
pub mod canonical;
pub mod config;
pub mod diagnostics;
pub mod dynamic;
pub mod evaluator;
pub mod messages;
pub mod planner;
pub mod runtime;
pub mod state;
pub mod test_model;
pub mod uera;
pub mod worker;

pub use config::{ClusterConfig, ExecutionConfig, Limits, NodeConfig};
pub use planner::{build_cluster_plan, ClusterPlan, ReasonTask};
pub use runtime::{run_cluster, ClusterRun, RunOptions};
