use crate::error::RuntimeError;
use crate::state::{State, StateManager};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Transition {
    pub relation: String,
}

impl Transition {
    pub fn new(relation: impl Into<String>) -> Self {
        Self {
            relation: relation.into(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TransitionCandidate {
    pub source: String,
    pub relation: String,
    pub target: String,
    pub expected_cost: f64,
}

impl TransitionCandidate {
    pub fn new(
        source: impl Into<String>,
        relation: impl Into<String>,
        target: impl Into<String>,
        expected_cost: f64,
    ) -> Self {
        Self {
            source: source.into(),
            relation: relation.into(),
            target: target.into(),
            expected_cost,
        }
    }

    pub fn id(&self) -> String {
        format!("{} --{}--> {}", self.source, self.relation, self.target)
    }
}

#[derive(Clone, Debug, Default)]
pub struct TransitionEngine {
    rules: Vec<TransitionCandidate>,
}

impl TransitionEngine {
    pub fn register(
        &mut self,
        source: impl Into<String>,
        relation: impl Into<String>,
        target: impl Into<String>,
    ) {
        self.register_candidate(TransitionCandidate::new(source, relation, target, 0.0));
    }

    pub fn register_with_cost(
        &mut self,
        source: impl Into<String>,
        relation: impl Into<String>,
        target: impl Into<String>,
        expected_cost: f64,
    ) {
        self.register_candidate(TransitionCandidate::new(
            source,
            relation,
            target,
            expected_cost,
        ));
    }

    pub fn register_candidate(&mut self, candidate: TransitionCandidate) {
        self.rules.push(candidate);
    }

    pub fn relation_count(&self) -> usize {
        self.rules.len()
    }

    pub fn outgoing(&self, source: &str) -> Vec<TransitionCandidate> {
        self.rules
            .iter()
            .filter(|candidate| candidate.source == source)
            .cloned()
            .collect()
    }

    pub fn parents(&self, source: &str) -> Vec<String> {
        self.rules
            .iter()
            .filter(|candidate| candidate.source == source && candidate.relation == "IsA")
            .map(|candidate| candidate.target.clone())
            .collect()
    }

    pub fn apply(
        &self,
        state_manager: &mut StateManager,
        transition: &Transition,
    ) -> Result<State, RuntimeError> {
        let source = state_manager.current().as_stable()?.identity.clone();
        let matches = self
            .rules
            .iter()
            .filter(|candidate| {
                candidate.source == source && candidate.relation == transition.relation
            })
            .collect::<Vec<_>>();
        if matches.is_empty() {
            return Err(RuntimeError::TransitionNotFound {
                source,
                relation: transition.relation.clone(),
            });
        }
        if matches.len() > 1 {
            return Err(RuntimeError::TransitionDecisionRequired {
                source,
                candidate_count: matches.len(),
            });
        }
        self.apply_candidate(state_manager, matches[0])
    }

    pub fn apply_candidate(
        &self,
        state_manager: &mut StateManager,
        candidate: &TransitionCandidate,
    ) -> Result<State, RuntimeError> {
        let source = state_manager.current().as_stable()?.identity.clone();
        if source != candidate.source
            || !self.rules.iter().any(|registered| registered == candidate)
        {
            return Err(RuntimeError::TransitionNotFound {
                source,
                relation: candidate.relation.clone(),
            });
        }
        let next = State::stable(candidate.target.clone());
        state_manager.replace(next.clone());
        Ok(next)
    }
}
