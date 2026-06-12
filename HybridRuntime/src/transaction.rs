use crate::reason_ir::{
    ReasonIrError, StateDelta, StateKernel, StateSnapshot, Trace, TransitionSpec,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ValidationStatus {
    Pending,
    Accepted,
    Rejected,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ValidationChecks {
    pub constraint: bool,
    pub guard: bool,
    pub policy: bool,
    pub budget: bool,
    pub state_consistency: bool,
}

impl ValidationChecks {
    pub fn accepted() -> Self {
        Self {
            constraint: true,
            guard: true,
            policy: true,
            budget: true,
            state_consistency: true,
        }
    }

    fn failures(&self) -> Vec<String> {
        [
            ("constraint", self.constraint),
            ("guard", self.guard),
            ("policy", self.policy),
            ("budget", self.budget),
            ("state_consistency", self.state_consistency),
        ]
        .into_iter()
        .filter(|(_, passed)| !passed)
        .map(|(name, _)| name.to_string())
        .collect()
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PreparedDelta {
    candidate_id: String,
    transaction_id: String,
    execution_plan_id: String,
    before_state: StateSnapshot,
    proposed_state: StateSnapshot,
    transition: TransitionSpec,
    validation_status: ValidationStatus,
    validation_failures: Vec<String>,
}

impl PreparedDelta {
    pub fn candidate_id(&self) -> &str {
        &self.candidate_id
    }

    pub fn transaction_id(&self) -> &str {
        &self.transaction_id
    }

    pub fn execution_plan_id(&self) -> &str {
        &self.execution_plan_id
    }

    pub fn before_state(&self) -> &StateSnapshot {
        &self.before_state
    }

    pub fn proposed_state(&self) -> &StateSnapshot {
        &self.proposed_state
    }

    pub fn transition(&self) -> &TransitionSpec {
        &self.transition
    }

    pub fn validation_status(&self) -> ValidationStatus {
        self.validation_status
    }

    pub fn validation_failures(&self) -> &[String] {
        &self.validation_failures
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TransactionStatus {
    Prepared,
    Accepted,
    Rejected,
    Committed,
    RolledBack,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TransactionRecord {
    pub transaction_id: String,
    pub execution_plan_id: String,
    pub candidate_id: String,
    pub delta_id: Option<String>,
    pub status: TransactionStatus,
    pub commit_timestamp: Option<u64>,
    pub validation_failures: Vec<String>,
    pub source_delta_id: Option<String>,
}

#[derive(Clone, Debug)]
pub struct TransactionKernel {
    state_kernel: StateKernel,
    trace: Trace,
    next_candidate_id: u64,
    candidates: BTreeMap<String, PreparedDelta>,
    transaction_ids: BTreeSet<String>,
    committed_candidates: BTreeSet<String>,
    rolled_back_deltas: BTreeSet<String>,
    deltas: Vec<StateDelta>,
    records: Vec<TransactionRecord>,
}

impl TransactionKernel {
    pub fn new(initial_state: StateSnapshot, trace: Trace) -> Self {
        Self {
            state_kernel: StateKernel::new(initial_state),
            trace,
            next_candidate_id: 1,
            candidates: BTreeMap::new(),
            transaction_ids: BTreeSet::new(),
            committed_candidates: BTreeSet::new(),
            rolled_back_deltas: BTreeSet::new(),
            deltas: Vec::new(),
            records: Vec::new(),
        }
    }

    pub fn current_state(&self) -> &StateSnapshot {
        self.state_kernel.current_state()
    }

    pub fn trace(&self) -> &Trace {
        &self.trace
    }

    pub fn deltas(&self) -> &[StateDelta] {
        &self.deltas
    }

    pub fn records(&self) -> &[TransactionRecord] {
        &self.records
    }

    pub fn prepared(&self, candidate_id: &str) -> Option<&PreparedDelta> {
        self.candidates.get(candidate_id)
    }

    pub fn prepare(
        &mut self,
        transaction_id: impl Into<String>,
        execution_plan_id: impl Into<String>,
        transition: TransitionSpec,
        proposed_state: StateSnapshot,
    ) -> Result<PreparedDelta, ReasonIrError> {
        let transaction_id = transaction_id.into();
        let execution_plan_id = execution_plan_id.into();
        require_id("transaction_id", &transaction_id)?;
        require_id("execution_plan_id", &execution_plan_id)?;
        if self.transaction_ids.contains(&transaction_id) {
            return Err(ReasonIrError::DuplicateTransactionId(transaction_id));
        }
        if transition.source != self.current_state().state_id {
            return Err(ReasonIrError::StateMismatch {
                expected: self.current_state().state_id.clone(),
                actual: transition.source,
            });
        }
        if transition.target != proposed_state.state_id {
            return Err(ReasonIrError::StateMismatch {
                expected: transition.target,
                actual: proposed_state.state_id,
            });
        }

        let candidate_id = format!("candidate-{}", self.next_candidate_id);
        self.next_candidate_id += 1;
        self.transaction_ids.insert(transaction_id.clone());
        let prepared = PreparedDelta {
            candidate_id: candidate_id.clone(),
            transaction_id: transaction_id.clone(),
            execution_plan_id: execution_plan_id.clone(),
            before_state: self.current_state().clone(),
            proposed_state,
            transition,
            validation_status: ValidationStatus::Pending,
            validation_failures: Vec::new(),
        };
        self.candidates
            .insert(candidate_id.clone(), prepared.clone());
        self.records.push(TransactionRecord {
            transaction_id,
            execution_plan_id,
            candidate_id,
            delta_id: None,
            status: TransactionStatus::Prepared,
            commit_timestamp: None,
            validation_failures: Vec::new(),
            source_delta_id: None,
        });
        Ok(prepared)
    }

    pub fn validate(
        &mut self,
        candidate_id: &str,
        checks: ValidationChecks,
    ) -> Result<ValidationStatus, ReasonIrError> {
        let candidate = self
            .candidates
            .get_mut(candidate_id)
            .ok_or_else(|| ReasonIrError::UnknownCandidate(candidate_id.to_string()))?;
        if candidate.validation_status != ValidationStatus::Pending {
            return Err(ReasonIrError::CandidateAlreadyValidated(
                candidate_id.to_string(),
            ));
        }
        let failures = checks.failures();
        candidate.validation_status = if failures.is_empty() {
            ValidationStatus::Accepted
        } else {
            ValidationStatus::Rejected
        };
        candidate.validation_failures = failures.clone();
        self.records.push(TransactionRecord {
            transaction_id: candidate.transaction_id.clone(),
            execution_plan_id: candidate.execution_plan_id.clone(),
            candidate_id: candidate_id.to_string(),
            delta_id: None,
            status: if failures.is_empty() {
                TransactionStatus::Accepted
            } else {
                TransactionStatus::Rejected
            },
            commit_timestamp: None,
            validation_failures: failures,
            source_delta_id: None,
        });
        Ok(candidate.validation_status)
    }

    pub fn commit(
        &mut self,
        candidate_id: &str,
        timestamp: u64,
    ) -> Result<StateDelta, ReasonIrError> {
        if self.committed_candidates.contains(candidate_id) {
            return Err(ReasonIrError::CandidateAlreadyCommitted(
                candidate_id.to_string(),
            ));
        }
        let candidate = self
            .candidates
            .get(candidate_id)
            .cloned()
            .ok_or_else(|| ReasonIrError::UnknownCandidate(candidate_id.to_string()))?;
        if candidate.validation_status != ValidationStatus::Accepted {
            return Err(ReasonIrError::CommitNotAllowed(candidate_id.to_string()));
        }
        if self.current_state() != &candidate.before_state {
            return Err(ReasonIrError::StateMismatch {
                expected: candidate.before_state.state_id,
                actual: self.current_state().state_id.clone(),
            });
        }

        let delta =
            self.state_kernel
                .apply(&candidate.transition, candidate.proposed_state, timestamp)?;
        self.trace
            .record_transaction_delta(&delta, &candidate.transaction_id);
        self.committed_candidates.insert(candidate_id.to_string());
        self.deltas.push(delta.clone());
        self.records.push(TransactionRecord {
            transaction_id: candidate.transaction_id,
            execution_plan_id: candidate.execution_plan_id,
            candidate_id: candidate_id.to_string(),
            delta_id: Some(delta.delta_id().to_string()),
            status: TransactionStatus::Committed,
            commit_timestamp: Some(timestamp),
            validation_failures: Vec::new(),
            source_delta_id: None,
        });
        Ok(delta)
    }

    pub fn rollback(
        &mut self,
        transaction_id: impl Into<String>,
        execution_plan_id: impl Into<String>,
        source_delta_id: &str,
        timestamp: u64,
    ) -> Result<StateDelta, ReasonIrError> {
        let transaction_id = transaction_id.into();
        let execution_plan_id = execution_plan_id.into();
        require_id("transaction_id", &transaction_id)?;
        require_id("execution_plan_id", &execution_plan_id)?;
        if self.transaction_ids.contains(&transaction_id) {
            return Err(ReasonIrError::DuplicateTransactionId(transaction_id));
        }
        if self.rolled_back_deltas.contains(source_delta_id) {
            return Err(ReasonIrError::DeltaAlreadyRolledBack(
                source_delta_id.to_string(),
            ));
        }
        let source = self
            .deltas
            .iter()
            .find(|delta| delta.delta_id() == source_delta_id)
            .cloned()
            .ok_or_else(|| ReasonIrError::UnknownDelta(source_delta_id.to_string()))?;
        let rollback = self.state_kernel.rollback(&source, timestamp)?;
        self.transaction_ids.insert(transaction_id.clone());
        self.rolled_back_deltas.insert(source_delta_id.to_string());
        self.trace
            .record_transaction_delta(&rollback, &transaction_id);
        self.deltas.push(rollback.clone());
        self.records.push(TransactionRecord {
            transaction_id,
            execution_plan_id,
            candidate_id: format!("rollback:{source_delta_id}"),
            delta_id: Some(rollback.delta_id().to_string()),
            status: TransactionStatus::RolledBack,
            commit_timestamp: Some(timestamp),
            validation_failures: Vec::new(),
            source_delta_id: Some(source_delta_id.to_string()),
        });
        Ok(rollback)
    }

    pub fn validate_trace_consistency(&self) -> Result<(), ReasonIrError> {
        self.trace.validate_deltas(&self.deltas)
    }
}

fn require_id(field: &str, value: &str) -> Result<(), ReasonIrError> {
    if value.trim().is_empty() {
        Err(ReasonIrError::MissingField(field.to_string()))
    } else {
        Ok(())
    }
}
