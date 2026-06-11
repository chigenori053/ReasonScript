use crate::error::RuntimeError;
use crate::state::AmbiguousState;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AmbiguityObservation {
    pub candidate_entropy: f64,
    pub normalized_entropy: f64,
    pub effective_candidate_count: f64,
    pub top_candidate_probability: f64,
    pub top_two_margin: f64,
    pub semantic_candidate_density: f64,
    pub evidence_conflict: f64,
    pub unsupported_evidence_ratio: f64,
}

#[derive(Clone, Debug, Default)]
pub struct AmbiguityEvaluator;

impl AmbiguityEvaluator {
    pub fn evaluate(&self, state: &AmbiguousState) -> Result<AmbiguityObservation, RuntimeError> {
        validate_state(state)?;

        let probabilities = normalized_probabilities(state);
        let entropy = probabilities
            .iter()
            .filter(|probability| **probability > 0.0)
            .map(|probability| -probability * probability.log2())
            .sum::<f64>();
        let normalized_entropy = if probabilities.len() <= 1 {
            0.0
        } else {
            entropy / (probabilities.len() as f64).log2()
        };

        let mut ranked = probabilities;
        ranked.sort_by(|left, right| right.total_cmp(left));
        let top = ranked[0];
        let second = ranked.get(1).copied().unwrap_or(0.0);

        Ok(AmbiguityObservation {
            candidate_entropy: entropy,
            normalized_entropy,
            effective_candidate_count: 2.0_f64.powf(entropy),
            top_candidate_probability: top,
            top_two_margin: top - second,
            semantic_candidate_density: semantic_density(state),
            evidence_conflict: evidence_conflict(state),
            unsupported_evidence_ratio: unsupported_ratio(state),
        })
    }
}

pub(crate) fn normalized_probabilities(state: &AmbiguousState) -> Vec<f64> {
    let total = state
        .candidates
        .iter()
        .map(|candidate| candidate.probability)
        .sum::<f64>();
    if total == 0.0 {
        vec![1.0 / state.candidates.len() as f64; state.candidates.len()]
    } else {
        state
            .candidates
            .iter()
            .map(|candidate| candidate.probability / total)
            .collect()
    }
}

fn validate_state(state: &AmbiguousState) -> Result<(), RuntimeError> {
    if state.candidates.is_empty() {
        return Err(RuntimeError::EmptyCandidates);
    }

    let semantic_dimension = state.candidates[0].semantic_vector.len();
    for candidate in &state.candidates {
        if !candidate.probability.is_finite() || candidate.probability < 0.0 {
            return Err(RuntimeError::InvalidProbability(candidate.identity.clone()));
        }
        if candidate.semantic_vector.len() != semantic_dimension
            || candidate
                .semantic_vector
                .iter()
                .any(|value| !value.is_finite())
        {
            return Err(RuntimeError::InvalidSemanticVector(
                candidate.identity.clone(),
            ));
        }
    }

    for evidence in state.evidence.iter().filter(|evidence| evidence.supported) {
        if evidence.candidate_support.len() != state.candidates.len()
            || evidence
                .candidate_support
                .iter()
                .any(|value| !value.is_finite())
        {
            return Err(RuntimeError::InvalidEvidence(evidence.label.clone()));
        }
    }
    Ok(())
}

fn semantic_density(state: &AmbiguousState) -> f64 {
    let mut total = 0.0;
    let mut count = 0;
    for left in 0..state.candidates.len() {
        for right in (left + 1)..state.candidates.len() {
            total += cosine_similarity(
                &state.candidates[left].semantic_vector,
                &state.candidates[right].semantic_vector,
            );
            count += 1;
        }
    }
    if count == 0 {
        0.0
    } else {
        total / count as f64
    }
}

fn evidence_conflict(state: &AmbiguousState) -> f64 {
    let supported: Vec<_> = state
        .evidence
        .iter()
        .filter(|evidence| evidence.supported)
        .collect();
    if supported.len() <= 1 {
        return 0.0;
    }

    let mut total = 0.0;
    let mut count = 0;
    for left in 0..supported.len() {
        for right in (left + 1)..supported.len() {
            total += 1.0
                - pearson_similarity(
                    &supported[left].candidate_support,
                    &supported[right].candidate_support,
                );
            count += 1;
        }
    }
    (total / count as f64).clamp(0.0, 1.0)
}

fn unsupported_ratio(state: &AmbiguousState) -> f64 {
    if state.evidence.is_empty() {
        return 0.0;
    }
    state
        .evidence
        .iter()
        .filter(|evidence| !evidence.supported)
        .count() as f64
        / state.evidence.len() as f64
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
        (dot / (left_norm * right_norm)).clamp(-1.0, 1.0)
    }
}

fn pearson_similarity(left: &[f64], right: &[f64]) -> f64 {
    let left_mean = left.iter().sum::<f64>() / left.len() as f64;
    let right_mean = right.iter().sum::<f64>() / right.len() as f64;
    let numerator = left
        .iter()
        .zip(right)
        .map(|(a, b)| (a - left_mean) * (b - right_mean))
        .sum::<f64>();
    let left_scale = left
        .iter()
        .map(|value| (value - left_mean).powi(2))
        .sum::<f64>()
        .sqrt();
    let right_scale = right
        .iter()
        .map(|value| (value - right_mean).powi(2))
        .sum::<f64>()
        .sqrt();
    if left_scale <= 1e-12 || right_scale <= 1e-12 {
        1.0
    } else {
        ((numerator / (left_scale * right_scale)) + 1.0) / 2.0
    }
}
