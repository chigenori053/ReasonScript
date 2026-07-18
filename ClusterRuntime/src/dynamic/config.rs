use serde::{Deserialize, Serialize};

use crate::diagnostics::Diagnostic;

pub const CONFIG_SCHEMA: &str = "reasonscript-dynamic-reason-unit-cluster-config/0.1";

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct LifecyclePolicy {
    #[serde(default = "yes")]
    pub allow_generation: bool,
    #[serde(default = "yes")]
    pub allow_suspension: bool,
    #[serde(default = "yes")]
    pub allow_reactivation: bool,
    #[serde(default = "yes")]
    pub allow_replacement: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DynamicLimits {
    #[serde(default = "thousand")]
    pub max_total_units: usize,
    #[serde(default = "thirty_two")]
    pub max_active_units: usize,
    #[serde(default = "one_twenty_eight")]
    pub max_units_per_branch: usize,
    #[serde(default = "eight")]
    pub max_generation_depth: usize,
    #[serde(default = "two_fifty_six")]
    pub max_proposals_per_epoch: usize,
    #[serde(default = "three")]
    pub max_reactivations_per_unit: usize,
    #[serde(default = "sixty_four")]
    pub max_branches: usize,
    #[serde(default = "five_hundred")]
    pub max_logical_steps: usize,
    #[serde(default = "state_bytes")]
    pub max_state_bytes: usize,
    #[serde(default = "messages")]
    pub max_messages: usize,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RevisionPolicy {
    #[serde(default = "boundary")]
    pub apply_at: String,
    #[serde(default = "yes")]
    pub atomic: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ConvergencePolicy {
    #[serde(default = "policies")]
    pub policies: Vec<String>,
    #[serde(default = "three")]
    pub stable_epochs: usize,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct PruningPolicy {
    #[serde(default = "yes")]
    pub duplicate_units: bool,
    #[serde(default = "yes")]
    pub duplicate_branches: bool,
    #[serde(default = "yes")]
    pub dominated_branches: bool,
    #[serde(default = "yes")]
    pub budget_pruning: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct FallbackPolicy {
    #[serde(default = "abort")]
    pub dynamic_failure: String,
    #[serde(default = "single_node")]
    pub worker_shortage: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DynamicConfig {
    pub schema_version: String,
    #[serde(default = "yes")]
    pub enabled: bool,
    #[serde(default)]
    pub lifecycle: LifecyclePolicy,
    #[serde(default)]
    pub limits: DynamicLimits,
    #[serde(default)]
    pub revision: RevisionPolicy,
    #[serde(default)]
    pub convergence: ConvergencePolicy,
    #[serde(default)]
    pub pruning: PruningPolicy,
    #[serde(default)]
    pub fallback: FallbackPolicy,
}

impl Default for DynamicConfig {
    fn default() -> Self {
        Self {
            schema_version: CONFIG_SCHEMA.into(),
            enabled: true,
            lifecycle: LifecyclePolicy::default(),
            limits: DynamicLimits::default(),
            revision: RevisionPolicy::default(),
            convergence: ConvergencePolicy::default(),
            pruning: PruningPolicy::default(),
            fallback: FallbackPolicy::default(),
        }
    }
}
impl Default for LifecyclePolicy {
    fn default() -> Self {
        Self {
            allow_generation: true,
            allow_suspension: true,
            allow_reactivation: true,
            allow_replacement: true,
        }
    }
}
impl Default for DynamicLimits {
    fn default() -> Self {
        Self {
            max_total_units: thousand(),
            max_active_units: thirty_two(),
            max_units_per_branch: one_twenty_eight(),
            max_generation_depth: eight(),
            max_proposals_per_epoch: two_fifty_six(),
            max_reactivations_per_unit: three(),
            max_branches: sixty_four(),
            max_logical_steps: five_hundred(),
            max_state_bytes: state_bytes(),
            max_messages: messages(),
        }
    }
}
impl Default for RevisionPolicy {
    fn default() -> Self {
        Self {
            apply_at: boundary(),
            atomic: true,
        }
    }
}
impl Default for ConvergencePolicy {
    fn default() -> Self {
        Self {
            policies: policies(),
            stable_epochs: three(),
        }
    }
}
impl Default for PruningPolicy {
    fn default() -> Self {
        Self {
            duplicate_units: true,
            duplicate_branches: true,
            dominated_branches: true,
            budget_pruning: true,
        }
    }
}
impl Default for FallbackPolicy {
    fn default() -> Self {
        Self {
            dynamic_failure: abort(),
            worker_shortage: single_node(),
        }
    }
}

impl DynamicConfig {
    pub fn validate(&self) -> Vec<Diagnostic> {
        let mut out = Vec::new();
        if self.schema_version != CONFIG_SCHEMA {
            out.push(Diagnostic::error(
                "DRU-PRP-001",
                "Unsupported dynamic configuration schema",
                "schema_version",
            ));
        }
        if !self.enabled {
            return out;
        }
        if self.limits.max_total_units == 0
            || self.limits.max_generation_depth == 0
            || self.limits.max_active_units == 0
        {
            out.push(Diagnostic::error(
                "DRU-GEN-003",
                "Dynamic reasoning limits must be bounded and non-zero",
                "limits",
            ));
        }
        if !self.revision.atomic || self.revision.apply_at != "logical_step_boundary" {
            out.push(Diagnostic::error(
                "DRU-REV-005",
                "v0.1 requires atomic logical-step-boundary revisions",
                "revision",
            ));
        }
        if self.convergence.policies.is_empty() {
            out.push(Diagnostic::error(
                "DRU-CNV-001",
                "A convergence policy is required",
                "convergence.policies",
            ));
        }
        out
    }
}
fn yes() -> bool {
    true
}
fn thousand() -> usize {
    1000
}
fn thirty_two() -> usize {
    32
}
fn one_twenty_eight() -> usize {
    128
}
fn eight() -> usize {
    8
}
fn two_fifty_six() -> usize {
    256
}
fn three() -> usize {
    3
}
fn sixty_four() -> usize {
    64
}
fn five_hundred() -> usize {
    500
}
fn state_bytes() -> usize {
    67_108_864
}
fn messages() -> usize {
    100_000
}
fn boundary() -> String {
    "logical_step_boundary".into()
}
fn policies() -> Vec<String> {
    vec!["quiescence".into(), "state_stable".into()]
}
fn abort() -> String {
    "abort".into()
}
fn single_node() -> String {
    "single_node".into()
}
