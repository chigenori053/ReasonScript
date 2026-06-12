use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

pub const REASON_IR_VERSION: &str = "reason-ir/0.1";

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct StateSnapshot {
    pub state_id: String,
    pub state_type: String,
    pub data: Value,
}

impl StateSnapshot {
    pub fn new(state_id: impl Into<String>, state_type: impl Into<String>, data: Value) -> Self {
        Self {
            state_id: state_id.into(),
            state_type: state_type.into(),
            data,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GoalSpec {
    pub kind: String,
    pub target: String,
}

impl GoalSpec {
    pub fn new(kind: impl Into<String>, target: impl Into<String>) -> Self {
        Self {
            kind: kind.into(),
            target: target.into(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ContextRef {
    pub context_id: String,
    pub context_type: String,
    pub uri: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConstraintSpec {
    pub constraint_id: String,
    pub kind: String,
    pub expression: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TransitionSpec {
    pub transition_id: String,
    pub source: String,
    pub relation: String,
    pub target: String,
    pub expected_cost: f64,
    pub guard: Option<String>,
    pub effect: Option<Value>,
}

impl TransitionSpec {
    pub fn new(
        transition_id: impl Into<String>,
        source: impl Into<String>,
        relation: impl Into<String>,
        target: impl Into<String>,
    ) -> Self {
        Self {
            transition_id: transition_id.into(),
            source: source.into(),
            relation: relation.into(),
            target: target.into(),
            expected_cost: 0.0,
            guard: None,
            effect: None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlannerPolicy {
    pub strategy: String,
    pub max_depth: Option<usize>,
    pub max_alternatives: Option<usize>,
}

impl Default for PlannerPolicy {
    fn default() -> Self {
        Self {
            strategy: "minimum_expected_cost".to_string(),
            max_depth: Some(128),
            max_alternatives: Some(8),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionPolicy {
    pub max_steps: usize,
    pub rollback_on_failure: bool,
    pub constraint_mode: String,
}

impl Default for ExecutionPolicy {
    fn default() -> Self {
        Self {
            max_steps: 128,
            rollback_on_failure: true,
            constraint_mode: "reject".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TracePolicy {
    pub level: String,
    pub include_alternatives: bool,
    pub include_state_data: bool,
}

impl Default for TracePolicy {
    fn default() -> Self {
        Self {
            level: "standard".to_string(),
            include_alternatives: true,
            include_state_data: true,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ReasonIR {
    pub schema_version: String,
    pub initial_state: StateSnapshot,
    pub goal: GoalSpec,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub context_refs: Vec<ContextRef>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub constraints: Vec<ConstraintSpec>,
    pub transitions: Vec<TransitionSpec>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub planner_policy: Option<PlannerPolicy>,
    pub execution_policy: ExecutionPolicy,
    pub trace_policy: TracePolicy,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, Value>,
}

impl ReasonIR {
    pub fn new(
        initial_state: StateSnapshot,
        goal: GoalSpec,
        transitions: Vec<TransitionSpec>,
    ) -> Self {
        Self {
            schema_version: REASON_IR_VERSION.to_string(),
            initial_state,
            goal,
            context_refs: Vec::new(),
            constraints: Vec::new(),
            transitions,
            planner_policy: None,
            execution_policy: ExecutionPolicy::default(),
            trace_policy: TracePolicy::default(),
            metadata: BTreeMap::new(),
        }
    }

    pub fn validate(&self) -> Result<(), ReasonIrError> {
        if self.schema_version != REASON_IR_VERSION {
            return Err(ReasonIrError::UnsupportedVersion(
                self.schema_version.clone(),
            ));
        }
        require_non_empty("initial_state.state_id", &self.initial_state.state_id)?;
        require_non_empty("initial_state.state_type", &self.initial_state.state_type)?;
        require_non_empty("goal.kind", &self.goal.kind)?;
        require_non_empty("goal.target", &self.goal.target)?;
        if self.execution_policy.max_steps == 0 {
            return Err(ReasonIrError::InvalidField(
                "execution_policy.max_steps".to_string(),
            ));
        }

        let mut transition_ids = BTreeSet::new();
        for transition in &self.transitions {
            require_non_empty("transition.transition_id", &transition.transition_id)?;
            require_non_empty("transition.source", &transition.source)?;
            require_non_empty("transition.relation", &transition.relation)?;
            require_non_empty("transition.target", &transition.target)?;
            if !transition.expected_cost.is_finite() || transition.expected_cost < 0.0 {
                return Err(ReasonIrError::InvalidField(format!(
                    "transition.expected_cost:{}",
                    transition.transition_id
                )));
            }
            if !transition_ids.insert(&transition.transition_id) {
                return Err(ReasonIrError::DuplicateId(transition.transition_id.clone()));
            }
        }
        Ok(())
    }

    pub fn to_json_pretty(&self) -> Result<String, ReasonIrError> {
        self.validate()?;
        serde_json::to_string_pretty(self)
            .map_err(|error| ReasonIrError::Serialization(error.to_string()))
    }

    pub fn from_json(input: &str) -> Result<Self, ReasonIrError> {
        let value: Value = serde_json::from_str(input)
            .map_err(|error| ReasonIrError::Serialization(error.to_string()))?;
        match value.get("schema_version").and_then(Value::as_str) {
            Some(REASON_IR_VERSION) => {
                let ir: Self = serde_json::from_value(value)
                    .map_err(|error| ReasonIrError::Serialization(error.to_string()))?;
                ir.validate()?;
                Ok(ir)
            }
            Some(version) => Err(ReasonIrError::UnsupportedVersion(version.to_string())),
            None => {
                let legacy: MinimalReasonIR = serde_json::from_value(value)
                    .map_err(|error| ReasonIrError::Serialization(error.to_string()))?;
                let ir = Self::from(legacy);
                ir.validate()?;
                Ok(ir)
            }
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct MinimalReasonIR {
    pub initial_state: StateSnapshot,
    pub transitions: Vec<TransitionSpec>,
    pub goal: GoalSpec,
}

impl From<MinimalReasonIR> for ReasonIR {
    fn from(legacy: MinimalReasonIR) -> Self {
        let mut ir = Self::new(legacy.initial_state, legacy.goal, legacy.transitions);
        ir.metadata.insert(
            "migrated_from".to_string(),
            Value::String("minimal-ir/unversioned".to_string()),
        );
        ir
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PlanStep {
    pub step_id: String,
    pub transition_id: String,
    pub source: String,
    pub target: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PlanPath {
    pub step_ids: Vec<String>,
    pub expected_cost: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ExecutionPlan {
    selected_steps: Vec<PlanStep>,
    alternative_paths: Vec<PlanPath>,
    expected_cost: f64,
    evidence_refs: Vec<String>,
    planner_version: String,
}

impl ExecutionPlan {
    pub fn new(
        selected_steps: Vec<PlanStep>,
        alternative_paths: Vec<PlanPath>,
        expected_cost: f64,
        evidence_refs: Vec<String>,
        planner_version: impl Into<String>,
    ) -> Result<Self, ReasonIrError> {
        if !expected_cost.is_finite() || expected_cost < 0.0 {
            return Err(ReasonIrError::InvalidField(
                "execution_plan.expected_cost".to_string(),
            ));
        }
        let plan = Self {
            selected_steps,
            alternative_paths,
            expected_cost,
            evidence_refs,
            planner_version: planner_version.into(),
        };
        require_non_empty("execution_plan.planner_version", &plan.planner_version)?;
        Ok(plan)
    }

    pub fn selected_steps(&self) -> &[PlanStep] {
        &self.selected_steps
    }

    pub fn alternative_paths(&self) -> &[PlanPath] {
        &self.alternative_paths
    }

    pub fn expected_cost(&self) -> f64 {
        self.expected_cost
    }

    pub fn evidence_refs(&self) -> &[String] {
        &self.evidence_refs
    }

    pub fn planner_version(&self) -> &str {
        &self.planner_version
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct StateDelta {
    delta_id: String,
    before_state: StateSnapshot,
    after_state: StateSnapshot,
    applied_transition: String,
    timestamp: u64,
}

impl StateDelta {
    pub fn delta_id(&self) -> &str {
        &self.delta_id
    }

    pub fn before_state(&self) -> &StateSnapshot {
        &self.before_state
    }

    pub fn after_state(&self) -> &StateSnapshot {
        &self.after_state
    }

    pub fn applied_transition(&self) -> &str {
        &self.applied_transition
    }

    pub fn timestamp(&self) -> u64 {
        self.timestamp
    }

    pub fn reversed(&self, delta_id: impl Into<String>, timestamp: u64) -> Self {
        Self {
            delta_id: delta_id.into(),
            before_state: self.after_state.clone(),
            after_state: self.before_state.clone(),
            applied_transition: format!("rollback:{}", self.applied_transition),
            timestamp,
        }
    }
}

#[derive(Clone, Debug)]
pub struct StateKernel {
    current_state: StateSnapshot,
    next_delta_id: u64,
}

impl StateKernel {
    pub fn new(initial_state: StateSnapshot) -> Self {
        Self {
            current_state: initial_state,
            next_delta_id: 1,
        }
    }

    pub fn current_state(&self) -> &StateSnapshot {
        &self.current_state
    }

    pub fn apply(
        &mut self,
        transition: &TransitionSpec,
        after_state: StateSnapshot,
        timestamp: u64,
    ) -> Result<StateDelta, ReasonIrError> {
        if transition.source != self.current_state.state_id {
            return Err(ReasonIrError::StateMismatch {
                expected: self.current_state.state_id.clone(),
                actual: transition.source.clone(),
            });
        }
        if transition.target != after_state.state_id {
            return Err(ReasonIrError::StateMismatch {
                expected: transition.target.clone(),
                actual: after_state.state_id,
            });
        }
        let delta = StateDelta {
            delta_id: format!("delta-{}", self.next_delta_id),
            before_state: self.current_state.clone(),
            after_state: after_state.clone(),
            applied_transition: transition.transition_id.clone(),
            timestamp,
        };
        self.next_delta_id += 1;
        self.current_state = after_state;
        Ok(delta)
    }

    pub fn rollback(
        &mut self,
        delta: &StateDelta,
        timestamp: u64,
    ) -> Result<StateDelta, ReasonIrError> {
        if self.current_state != delta.after_state {
            return Err(ReasonIrError::StateMismatch {
                expected: delta.after_state.state_id.clone(),
                actual: self.current_state.state_id.clone(),
            });
        }
        let reversed = delta.reversed(format!("delta-{}", self.next_delta_id), timestamp);
        self.next_delta_id += 1;
        self.current_state = reversed.after_state.clone();
        Ok(reversed)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum InferenceStatus {
    Completed,
    Rejected,
    DecisionRequired,
    Failed,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Proof {
    pub selected_step_ids: Vec<String>,
    pub evidence_refs: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Violation {
    pub constraint_id: String,
    pub message: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct InferenceResult {
    pub status: InferenceStatus,
    pub final_state: StateSnapshot,
    pub state_deltas: Vec<StateDelta>,
    pub proof: Option<Proof>,
    pub violations: Vec<Violation>,
    pub alternatives: Vec<PlanPath>,
    pub trace_id: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "event_type", rename_all = "snake_case")]
pub enum TraceEvent {
    PlanSelected {
        step_ids: Vec<String>,
        expected_cost: f64,
    },
    StateDeltaApplied {
        delta_id: String,
        transition_id: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        transaction_id: Option<String>,
    },
    ConstraintViolation {
        constraint_id: String,
        message: String,
    },
    EvidenceObserved {
        evidence_ref: String,
    },
    ToolInvoked {
        tool_ref: String,
        result_ref: String,
    },
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Trace {
    pub request_id: String,
    pub reason_ir_version: String,
    pub planner_version: Option<String>,
    pub policy_version: String,
    pub events: Vec<TraceEvent>,
}

impl Trace {
    pub fn new(
        request_id: impl Into<String>,
        planner_version: Option<String>,
        policy_version: impl Into<String>,
    ) -> Self {
        Self {
            request_id: request_id.into(),
            reason_ir_version: REASON_IR_VERSION.to_string(),
            planner_version,
            policy_version: policy_version.into(),
            events: Vec::new(),
        }
    }

    pub fn record_delta(&mut self, delta: &StateDelta) {
        self.events.push(TraceEvent::StateDeltaApplied {
            delta_id: delta.delta_id.clone(),
            transition_id: delta.applied_transition.clone(),
            transaction_id: None,
        });
    }

    pub fn record_transaction_delta(&mut self, delta: &StateDelta, transaction_id: &str) {
        self.events.push(TraceEvent::StateDeltaApplied {
            delta_id: delta.delta_id.clone(),
            transition_id: delta.applied_transition.clone(),
            transaction_id: Some(transaction_id.to_string()),
        });
    }

    pub fn validate_deltas(&self, deltas: &[StateDelta]) -> Result<(), ReasonIrError> {
        let event_delta_ids = self
            .events
            .iter()
            .filter_map(|event| match event {
                TraceEvent::StateDeltaApplied { delta_id, .. } => Some(delta_id.as_str()),
                _ => None,
            })
            .collect::<BTreeSet<_>>();
        for delta in deltas {
            if !event_delta_ids.contains(delta.delta_id.as_str()) {
                return Err(ReasonIrError::MissingTraceEvent(delta.delta_id.clone()));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ReasonIrError {
    Serialization(String),
    UnsupportedVersion(String),
    MissingField(String),
    InvalidField(String),
    DuplicateId(String),
    StateMismatch { expected: String, actual: String },
    MissingTraceEvent(String),
    DuplicateTransactionId(String),
    UnknownCandidate(String),
    CandidateAlreadyValidated(String),
    CandidateAlreadyCommitted(String),
    CommitNotAllowed(String),
    UnknownDelta(String),
    DeltaAlreadyRolledBack(String),
}

impl fmt::Display for ReasonIrError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Serialization(message) => write!(formatter, "serialization failed: {message}"),
            Self::UnsupportedVersion(version) => {
                write!(formatter, "unsupported Reason IR version: {version}")
            }
            Self::MissingField(field) => write!(formatter, "missing required field: {field}"),
            Self::InvalidField(field) => write!(formatter, "invalid field: {field}"),
            Self::DuplicateId(id) => write!(formatter, "duplicate id: {id}"),
            Self::StateMismatch { expected, actual } => {
                write!(
                    formatter,
                    "state mismatch: expected {expected}, actual {actual}"
                )
            }
            Self::MissingTraceEvent(delta_id) => {
                write!(formatter, "missing trace event for delta: {delta_id}")
            }
            Self::DuplicateTransactionId(id) => write!(formatter, "duplicate transaction id: {id}"),
            Self::UnknownCandidate(id) => write!(formatter, "unknown delta candidate: {id}"),
            Self::CandidateAlreadyValidated(id) => {
                write!(formatter, "delta candidate already validated: {id}")
            }
            Self::CandidateAlreadyCommitted(id) => {
                write!(formatter, "delta candidate already committed: {id}")
            }
            Self::CommitNotAllowed(id) => {
                write!(
                    formatter,
                    "delta candidate is not accepted for commit: {id}"
                )
            }
            Self::UnknownDelta(id) => write!(formatter, "unknown state delta: {id}"),
            Self::DeltaAlreadyRolledBack(id) => {
                write!(formatter, "state delta already rolled back: {id}")
            }
        }
    }
}

impl std::error::Error for ReasonIrError {}

fn require_non_empty(field: &str, value: &str) -> Result<(), ReasonIrError> {
    if value.trim().is_empty() {
        Err(ReasonIrError::MissingField(field.to_string()))
    } else {
        Ok(())
    }
}
