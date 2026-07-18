use std::collections::HashSet;

use serde::{Deserialize, Serialize};

use crate::diagnostics::{sort, Diagnostic};

pub const CONFIG_SCHEMA: &str = "reasonscript-cluster-config/0.1";

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct NodeConfig {
    pub node_id: String,
    #[serde(default = "one")]
    pub capacity: usize,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ExecutionConfig {
    #[serde(default = "default_sync")]
    pub sync_policy: String,
    #[serde(default = "one")]
    pub max_retries: usize,
    #[serde(default = "default_fallback")]
    pub fallback: String,
    #[serde(default = "yes")]
    pub deterministic: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Limits {
    #[serde(default = "eight")]
    pub max_workers: usize,
    #[serde(default = "ten_thousand")]
    pub max_tasks: usize,
    #[serde(default = "one_thousand")]
    pub max_logical_steps: usize,
    #[serde(default = "one_megabyte")]
    pub max_message_bytes: usize,
    #[serde(default = "sixty_four_megabytes")]
    pub max_state_bytes: usize,
    #[serde(default = "thirty_seconds")]
    pub task_timeout_ms: u64,
    #[serde(default = "one_second")]
    pub heartbeat_interval_ms: u64,
    #[serde(default = "three")]
    pub heartbeat_miss_limit: usize,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct TestingConfig {
    #[serde(default)]
    pub fail_task_once: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ClusterConfig {
    pub schema_version: String,
    pub cluster_id: String,
    pub mode: String,
    pub coordinator: NodeConfig,
    pub workers: Vec<NodeConfig>,
    pub execution: ExecutionConfig,
    #[serde(default)]
    pub limits: Limits,
    #[serde(default)]
    pub testing: Option<TestingConfig>,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            max_workers: eight(),
            max_tasks: ten_thousand(),
            max_logical_steps: one_thousand(),
            max_message_bytes: one_megabyte(),
            max_state_bytes: sixty_four_megabytes(),
            task_timeout_ms: thirty_seconds(),
            heartbeat_interval_ms: one_second(),
            heartbeat_miss_limit: three(),
        }
    }
}

impl ClusterConfig {
    pub fn local(workers: usize, mode: &str) -> Self {
        Self {
            schema_version: CONFIG_SCHEMA.into(),
            cluster_id: "local_cluster".into(),
            mode: mode.into(),
            coordinator: NodeConfig {
                node_id: "coordinator-0".into(),
                capacity: 1,
            },
            workers: (0..workers)
                .map(|i| NodeConfig {
                    node_id: format!("worker-{i}"),
                    capacity: 1,
                })
                .collect(),
            execution: ExecutionConfig {
                sync_policy: default_sync(),
                max_retries: 1,
                fallback: default_fallback(),
                deterministic: true,
            },
            limits: Limits::default(),
            testing: None,
        }
    }

    pub fn validate(&self) -> Vec<Diagnostic> {
        let mut result = Vec::new();
        if self.schema_version != CONFIG_SCHEMA {
            result.push(Diagnostic::error(
                "CRR-CFG-002",
                "Unsupported schema_version",
                "schema_version",
            ));
        }
        if !matches!(
            self.mode.as_str(),
            "single_process" | "local_process" | "simulation"
        ) {
            result.push(Diagnostic::error(
                "CRR-CFG-004",
                "Invalid execution mode",
                "mode",
            ));
        }
        if self.workers.is_empty() {
            result.push(Diagnostic::error(
                "CRR-CFG-005",
                "Insufficient worker count",
                "workers",
            ));
        }
        let ids: HashSet<_> = self.workers.iter().map(|w| &w.node_id).collect();
        if ids.len() != self.workers.len() {
            result.push(Diagnostic::error(
                "CRR-CFG-003",
                "Duplicate worker ID",
                "workers",
            ));
        }
        if self.workers.len() > self.limits.max_workers {
            result.push(Diagnostic::error(
                "CRR-CFG-005",
                "Worker count exceeds max_workers",
                "workers",
            ));
        }
        if !matches!(
            self.execution.fallback.as_str(),
            "none" | "single_node" | "abort" | "partial"
        ) {
            result.push(Diagnostic::error(
                "CRR-CFG-006",
                "Invalid fallback policy",
                "execution.fallback",
            ));
        }
        if !matches!(
            self.execution.sync_policy.as_str(),
            "none" | "barrier" | "coordinator"
        ) {
            result.push(Diagnostic::error(
                "CRR-CFG-004",
                "Invalid sync policy",
                "execution.sync_policy",
            ));
        }
        if !self.execution.deterministic {
            result.push(Diagnostic::error(
                "CRR-PLN-005",
                "v0.1 requires deterministic execution",
                "execution.deterministic",
            ));
        }
        sort(&mut result);
        result
    }
}

fn one() -> usize {
    1
}
fn three() -> usize {
    3
}
fn eight() -> usize {
    8
}
fn ten_thousand() -> usize {
    10_000
}
fn one_thousand() -> usize {
    1_000
}
fn one_megabyte() -> usize {
    1_048_576
}
fn sixty_four_megabytes() -> usize {
    67_108_864
}
fn thirty_seconds() -> u64 {
    30_000
}
fn one_second() -> u64 {
    1_000
}
fn yes() -> bool {
    true
}
fn default_sync() -> String {
    "barrier".into()
}
fn default_fallback() -> String {
    "single_node".into()
}
