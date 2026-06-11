use crate::ambiguity::{normalized_probabilities, AmbiguityEvaluator};
use crate::decision::{DecisionEngine, DecisionInput, RiskPolicy, TransitionDecisionInput};
use crate::error::RuntimeError;
use crate::resolver::IdentityResolver;
use crate::state::{HybridReasonUnit, State, StateManager};
use crate::strategy::ResolutionOutcome;
use crate::trace::{TraceLogger, TraceRecord};
use crate::transition::{Transition, TransitionEngine};

pub struct HybridRuntime {
    pub state_manager: StateManager,
    pub ambiguity_evaluator: AmbiguityEvaluator,
    pub decision_engine: DecisionEngine,
    pub identity_resolver: IdentityResolver,
    pub transition_engine: TransitionEngine,
    pub trace_logger: TraceLogger,
    pub risk_policy: RiskPolicy,
    pub policy_version: String,
    pub evaluator_version: String,
    trace_test_id: Option<String>,
}

impl HybridRuntime {
    pub fn new(unit: HybridReasonUnit) -> Self {
        Self {
            state_manager: StateManager::new(unit),
            ambiguity_evaluator: AmbiguityEvaluator,
            decision_engine: DecisionEngine,
            identity_resolver: IdentityResolver::default(),
            transition_engine: TransitionEngine::default(),
            trace_logger: TraceLogger::default(),
            risk_policy: RiskPolicy::default(),
            policy_version: "hybrid-runtime-v0.2-default".to_string(),
            evaluator_version: "ambiguity-evaluator-v0.2".to_string(),
            trace_test_id: None,
        }
    }

    pub fn set_trace_test_id(&mut self, test_id: impl Into<String>) {
        self.trace_test_id = Some(test_id.into());
    }

    pub fn resolve_identity(&mut self) -> Result<ResolutionOutcome, RuntimeError> {
        let ambiguous = self.state_manager.current().as_ambiguous()?.clone();
        let observation = self.ambiguity_evaluator.evaluate(&ambiguous)?;
        let available = self.identity_resolver.available_strategies();
        let decision = self.decision_engine.decide(DecisionInput {
            ambiguity_observation: &observation,
            available_strategies: &available,
            risk_policy: &self.risk_policy,
        })?;
        let outcome = self
            .identity_resolver
            .resolve(&ambiguous, &observation, &decision)?;

        let distribution = ambiguous
            .candidates
            .iter()
            .zip(normalized_probabilities(&ambiguous))
            .map(|(candidate, probability)| (candidate.identity.clone(), probability))
            .collect();
        let mut trace = TraceRecord::resolution(
            State::ambiguous(ambiguous.candidates.clone(), ambiguous.evidence.clone()),
            distribution,
            observation,
            decision,
            &outcome,
            self.policy_version.clone(),
            self.evaluator_version.clone(),
        );
        if let Some(test_id) = &self.trace_test_id {
            trace = trace.with_test_id(test_id.clone());
        }
        self.trace_logger.record(trace);

        if let ResolutionOutcome::Resolved(stable) = &outcome {
            self.state_manager
                .replace(State::stable(stable.identity.clone()));
        }
        Ok(outcome)
    }

    pub fn transition(&mut self, transition: Transition) -> Result<State, RuntimeError> {
        let initial_state = self.state_manager.current().clone();
        let next_state = self
            .transition_engine
            .apply(&mut self.state_manager, &transition)?;
        let mut trace = TraceRecord::transition(
            initial_state,
            transition.relation,
            next_state.clone(),
            self.policy_version.clone(),
            self.evaluator_version.clone(),
        );
        if let Some(test_id) = &self.trace_test_id {
            trace = trace.with_test_id(test_id.clone());
        }
        self.trace_logger.record(trace);
        Ok(next_state)
    }

    pub fn decide_and_transition(&mut self) -> Result<State, RuntimeError> {
        let initial_state = self.state_manager.current().clone();
        let source = initial_state.as_stable()?.identity.clone();
        let available = self.transition_engine.outgoing(&source);
        if available.is_empty() {
            return Err(RuntimeError::TransitionNotFound {
                source,
                relation: "*".to_string(),
            });
        }
        let decision = match self
            .decision_engine
            .decide_transition(TransitionDecisionInput {
                candidates: &available,
            }) {
            Ok(decision) => decision,
            Err(error @ RuntimeError::TransitionDecisionRequired { .. }) => {
                let mut trace = TraceRecord::transition_conflict(
                    initial_state,
                    available,
                    self.policy_version.clone(),
                    self.evaluator_version.clone(),
                );
                if let Some(test_id) = &self.trace_test_id {
                    trace = trace.with_test_id(test_id.clone());
                }
                self.trace_logger.record(trace);
                return Err(error);
            }
            Err(error) => return Err(error),
        };
        let next_state = self
            .transition_engine
            .apply_candidate(&mut self.state_manager, &decision.selected_transition)?;
        let mut trace = TraceRecord::transition_decision(
            initial_state,
            available,
            decision,
            next_state.clone(),
            self.policy_version.clone(),
            self.evaluator_version.clone(),
        );
        if let Some(test_id) = &self.trace_test_id {
            trace = trace.with_test_id(test_id.clone());
        }
        self.trace_logger.record(trace);
        Ok(next_state)
    }
}
