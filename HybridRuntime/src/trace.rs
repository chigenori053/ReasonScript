use crate::ambiguity::AmbiguityObservation;
use crate::decision::{DecisionResult, StrategyKind, TransitionDecisionResult};
use crate::error::RuntimeError;
use crate::state::State;
use crate::strategy::ResolutionOutcome;
use crate::transition::TransitionCandidate;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum TraceEventKind {
    Resolution,
    Transition,
    TransitionConflict,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TraceRecord {
    pub test_id: Option<String>,
    pub event_kind: TraceEventKind,
    pub trace_event_kind: TraceEventKind,
    pub initial_state: State,
    pub candidate_distribution: Vec<(String, f64)>,
    pub ambiguity_observation: Option<AmbiguityObservation>,
    pub selected_strategy: Option<StrategyKind>,
    pub alternative_strategies: Vec<StrategyKind>,
    pub decision_reason: Option<String>,
    pub strategy_scores: BTreeMap<StrategyKind, f64>,
    pub selected_to_next_score_gap: Option<f64>,
    pub confidence: Option<f64>,
    pub resolution_outcome: Option<String>,
    pub transition_relation: Option<String>,
    pub available_transitions: Vec<TransitionCandidate>,
    pub selected_transition: Option<TransitionCandidate>,
    pub alternative_transitions: Vec<TransitionCandidate>,
    pub transition_scores: BTreeMap<String, f64>,
    pub next_state: Option<State>,
    pub policy_version: String,
    pub evaluator_version: String,
}

impl TraceRecord {
    pub fn resolution(
        initial_state: State,
        candidate_distribution: Vec<(String, f64)>,
        ambiguity_observation: AmbiguityObservation,
        decision: DecisionResult,
        outcome: &ResolutionOutcome,
        policy_version: impl Into<String>,
        evaluator_version: impl Into<String>,
    ) -> Self {
        let selected_score = decision.strategy_scores[&decision.selected_strategy];
        let selected_to_next_score_gap = decision
            .alternative_strategies
            .first()
            .map(|alternative| decision.strategy_scores[alternative] - selected_score);
        Self {
            test_id: None,
            event_kind: TraceEventKind::Resolution,
            trace_event_kind: TraceEventKind::Resolution,
            initial_state,
            candidate_distribution,
            ambiguity_observation: Some(ambiguity_observation),
            selected_strategy: Some(decision.selected_strategy),
            alternative_strategies: decision.alternative_strategies,
            decision_reason: Some(decision.decision_reason),
            strategy_scores: decision.strategy_scores,
            selected_to_next_score_gap,
            confidence: Some(decision.confidence),
            resolution_outcome: Some(describe_outcome(outcome)),
            transition_relation: None,
            available_transitions: Vec::new(),
            selected_transition: None,
            alternative_transitions: Vec::new(),
            transition_scores: BTreeMap::new(),
            next_state: match outcome {
                ResolutionOutcome::Resolved(stable) => Some(State::stable(stable.identity.clone())),
                ResolutionOutcome::Deferred { state, .. } => Some(State::ambiguous(
                    state.candidates.clone(),
                    state.evidence.clone(),
                )),
            },
            policy_version: policy_version.into(),
            evaluator_version: evaluator_version.into(),
        }
    }

    pub fn transition(
        initial_state: State,
        relation: impl Into<String>,
        next_state: State,
        policy_version: impl Into<String>,
        evaluator_version: impl Into<String>,
    ) -> Self {
        Self {
            test_id: None,
            event_kind: TraceEventKind::Transition,
            trace_event_kind: TraceEventKind::Transition,
            initial_state,
            candidate_distribution: Vec::new(),
            ambiguity_observation: None,
            selected_strategy: None,
            alternative_strategies: Vec::new(),
            decision_reason: Some("registered transition rule applied".to_string()),
            strategy_scores: BTreeMap::new(),
            selected_to_next_score_gap: None,
            confidence: None,
            resolution_outcome: None,
            transition_relation: Some(relation.into()),
            available_transitions: Vec::new(),
            selected_transition: None,
            alternative_transitions: Vec::new(),
            transition_scores: BTreeMap::new(),
            next_state: Some(next_state),
            policy_version: policy_version.into(),
            evaluator_version: evaluator_version.into(),
        }
    }

    pub fn transition_decision(
        initial_state: State,
        available_transitions: Vec<TransitionCandidate>,
        decision: TransitionDecisionResult,
        next_state: State,
        policy_version: impl Into<String>,
        evaluator_version: impl Into<String>,
    ) -> Self {
        Self {
            test_id: None,
            event_kind: TraceEventKind::Transition,
            trace_event_kind: TraceEventKind::Transition,
            initial_state,
            candidate_distribution: Vec::new(),
            ambiguity_observation: None,
            selected_strategy: None,
            alternative_strategies: Vec::new(),
            decision_reason: Some(decision.decision_reason),
            strategy_scores: BTreeMap::new(),
            selected_to_next_score_gap: decision.selected_to_next_score_gap,
            confidence: None,
            resolution_outcome: None,
            transition_relation: Some(decision.selected_transition.relation.clone()),
            available_transitions,
            selected_transition: Some(decision.selected_transition),
            alternative_transitions: decision.alternative_transitions,
            transition_scores: decision.transition_scores,
            next_state: Some(next_state),
            policy_version: policy_version.into(),
            evaluator_version: evaluator_version.into(),
        }
    }

    pub fn transition_conflict(
        initial_state: State,
        available_transitions: Vec<TransitionCandidate>,
        policy_version: impl Into<String>,
        evaluator_version: impl Into<String>,
    ) -> Self {
        let transition_scores = available_transitions
            .iter()
            .map(|candidate| (candidate.id(), candidate.expected_cost))
            .collect();
        Self {
            test_id: None,
            event_kind: TraceEventKind::TransitionConflict,
            trace_event_kind: TraceEventKind::TransitionConflict,
            initial_state,
            candidate_distribution: Vec::new(),
            ambiguity_observation: None,
            selected_strategy: None,
            alternative_strategies: Vec::new(),
            decision_reason: Some(
                "equal minimum expected transition cost; decision required".to_string(),
            ),
            strategy_scores: BTreeMap::new(),
            selected_to_next_score_gap: Some(0.0),
            confidence: None,
            resolution_outcome: None,
            transition_relation: None,
            available_transitions: available_transitions.clone(),
            selected_transition: None,
            alternative_transitions: available_transitions,
            transition_scores,
            next_state: None,
            policy_version: policy_version.into(),
            evaluator_version: evaluator_version.into(),
        }
    }

    pub fn with_test_id(mut self, test_id: impl Into<String>) -> Self {
        self.test_id = Some(test_id.into());
        self
    }
}

#[derive(Clone, Debug, Default)]
pub struct TraceLogger {
    records: Vec<TraceRecord>,
}

impl TraceLogger {
    pub fn record(&mut self, record: TraceRecord) {
        self.records.push(record);
    }

    pub fn records(&self) -> &[TraceRecord] {
        &self.records
    }

    pub fn to_json_pretty(&self) -> Result<String, RuntimeError> {
        serde_json::to_string_pretty(&self.records)
            .map_err(|error| RuntimeError::TraceSerialization(error.to_string()))
    }
}

fn describe_outcome(outcome: &ResolutionOutcome) -> String {
    match outcome {
        ResolutionOutcome::Resolved(stable) => {
            format!("Resolved({})", stable.identity)
        }
        ResolutionOutcome::Deferred {
            requested_evidence, ..
        } => format!("Deferred({requested_evidence})"),
    }
}
