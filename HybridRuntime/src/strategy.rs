use crate::ambiguity::{normalized_probabilities, AmbiguityObservation};
use crate::decision::StrategyKind;
use crate::error::RuntimeError;
use crate::state::{AmbiguousState, StableState};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum ResolutionOutcome {
    Resolved(StableState),
    Deferred {
        state: AmbiguousState,
        requested_evidence: String,
    },
}

pub trait ResolutionStrategy {
    fn kind(&self) -> StrategyKind;

    fn resolve(
        &self,
        state: &AmbiguousState,
        observation: &AmbiguityObservation,
    ) -> Result<ResolutionOutcome, RuntimeError>;
}

#[derive(Clone, Debug, Default)]
pub struct RealStrategy;

impl ResolutionStrategy for RealStrategy {
    fn kind(&self) -> StrategyKind {
        StrategyKind::Real
    }

    fn resolve(
        &self,
        state: &AmbiguousState,
        _observation: &AmbiguityObservation,
    ) -> Result<ResolutionOutcome, RuntimeError> {
        let probabilities = normalized_probabilities(state);
        let index = probabilities
            .iter()
            .enumerate()
            .max_by(|left, right| left.1.total_cmp(right.1))
            .map(|(index, _)| index)
            .ok_or(RuntimeError::EmptyCandidates)?;
        Ok(ResolutionOutcome::Resolved(StableState::new(
            state.candidates[index].identity.clone(),
        )))
    }
}

#[derive(Clone, Debug, Default)]
pub struct ClarifyStrategy;

impl ResolutionStrategy for ClarifyStrategy {
    fn kind(&self) -> StrategyKind {
        StrategyKind::Clarify
    }

    fn resolve(
        &self,
        state: &AmbiguousState,
        observation: &AmbiguityObservation,
    ) -> Result<ResolutionOutcome, RuntimeError> {
        Ok(ResolutionOutcome::Deferred {
            state: state.clone(),
            requested_evidence: format!(
                "request evidence that separates the top candidates; current margin={:.6}",
                observation.top_two_margin
            ),
        })
    }
}

#[derive(Clone, Debug, Default)]
pub struct ComplexStrategy;

impl ResolutionStrategy for ComplexStrategy {
    fn kind(&self) -> StrategyKind {
        StrategyKind::Complex
    }

    fn resolve(
        &self,
        state: &AmbiguousState,
        observation: &AmbiguityObservation,
    ) -> Result<ResolutionOutcome, RuntimeError> {
        let probabilities = normalized_probabilities(state);
        let mut best: Option<(usize, f64)> = None;
        for (index, probability) in probabilities.iter().copied().enumerate() {
            let centrality = average_similarity(index, state);
            let competition_score =
                probability * (1.0 + observation.evidence_conflict * centrality.max(0.0));
            if best
                .map(|(_, score)| competition_score > score)
                .unwrap_or(true)
            {
                best = Some((index, competition_score));
            }
        }
        let index = best
            .map(|(index, _)| index)
            .ok_or(RuntimeError::EmptyCandidates)?;
        Ok(ResolutionOutcome::Resolved(StableState::new(
            state.candidates[index].identity.clone(),
        )))
    }
}

fn average_similarity(candidate_index: usize, state: &AmbiguousState) -> f64 {
    if state.candidates.len() <= 1 {
        return 0.0;
    }
    let candidate = &state.candidates[candidate_index].semantic_vector;
    let total = state
        .candidates
        .iter()
        .enumerate()
        .filter(|(index, _)| *index != candidate_index)
        .map(|(_, other)| cosine_similarity(candidate, &other.semantic_vector))
        .sum::<f64>();
    total / (state.candidates.len() - 1) as f64
}

fn cosine_similarity(left: &[f64], right: &[f64]) -> f64 {
    if left.is_empty() || right.is_empty() {
        return 0.0;
    }
    let dot = left.iter().zip(right).map(|(a, b)| a * b).sum::<f64>();
    let left_norm = left.iter().map(|value| value * value).sum::<f64>().sqrt();
    let right_norm = right.iter().map(|value| value * value).sum::<f64>().sqrt();
    if left_norm == 0.0 || right_norm == 0.0 {
        0.0
    } else {
        dot / (left_norm * right_norm)
    }
}
