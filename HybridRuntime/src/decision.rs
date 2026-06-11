use crate::ambiguity::AmbiguityObservation;
use crate::error::RuntimeError;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

use crate::transition::TransitionCandidate;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum StrategyKind {
    Real,
    Clarify,
    Complex,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RiskPolicy {
    pub wrong_identity_cost: f64,
    pub conflict_cost: f64,
    pub unsupported_evidence_cost: f64,
    pub clarify_base_cost: f64,
    pub clarify_residual_risk: f64,
    pub complex_base_cost: f64,
    pub complex_residual_risk: f64,
}

impl Default for RiskPolicy {
    fn default() -> Self {
        Self {
            wrong_identity_cost: 4.0,
            conflict_cost: 1.5,
            unsupported_evidence_cost: 0.5,
            clarify_base_cost: 0.45,
            clarify_residual_risk: 1.2,
            complex_base_cost: 0.90,
            complex_residual_risk: 0.35,
        }
    }
}

#[derive(Clone, Debug)]
pub struct DecisionInput<'a> {
    pub ambiguity_observation: &'a AmbiguityObservation,
    pub available_strategies: &'a [StrategyKind],
    pub risk_policy: &'a RiskPolicy,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct DecisionResult {
    pub selected_strategy: StrategyKind,
    pub alternative_strategies: Vec<StrategyKind>,
    pub decision_reason: String,
    pub strategy_scores: BTreeMap<StrategyKind, f64>,
    pub confidence: f64,
}

#[derive(Clone, Debug, Default)]
pub struct DecisionEngine;

#[derive(Clone, Debug)]
pub struct TransitionDecisionInput<'a> {
    pub candidates: &'a [TransitionCandidate],
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TransitionDecisionResult {
    pub selected_transition: TransitionCandidate,
    pub alternative_transitions: Vec<TransitionCandidate>,
    pub decision_reason: String,
    pub transition_scores: BTreeMap<String, f64>,
    pub selected_to_next_score_gap: Option<f64>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphPathCandidate {
    pub nodes: Vec<String>,
    pub edges: Vec<String>,
    pub total_cost: f64,
}

impl GraphPathCandidate {
    pub fn id(&self) -> String {
        self.nodes.join(" -> ")
    }
}

#[derive(Clone, Debug)]
pub struct GraphDecisionInput<'a> {
    pub source: &'a str,
    pub candidates: &'a [GraphPathCandidate],
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphDecisionResult {
    pub selected_path: GraphPathCandidate,
    pub alternative_paths: Vec<GraphPathCandidate>,
    pub decision_reason: String,
    pub path_scores: BTreeMap<String, f64>,
    pub selected_to_next_score_gap: Option<f64>,
}

impl DecisionEngine {
    pub fn decide(&self, input: DecisionInput<'_>) -> Result<DecisionResult, RuntimeError> {
        if input.available_strategies.is_empty() {
            return Err(RuntimeError::NoAvailableStrategy);
        }

        let observation = input.ambiguity_observation;
        let policy = input.risk_policy;
        let error_probability = 1.0 - observation.top_candidate_probability;
        let all_scores = BTreeMap::from([
            (
                StrategyKind::Real,
                policy.wrong_identity_cost * error_probability
                    + policy.conflict_cost * observation.evidence_conflict
                    + policy.unsupported_evidence_cost * observation.unsupported_evidence_ratio,
            ),
            (
                StrategyKind::Clarify,
                policy.clarify_base_cost
                    + policy.clarify_residual_risk * error_probability
                    + 0.40 * observation.evidence_conflict,
            ),
            (
                StrategyKind::Complex,
                policy.complex_base_cost
                    + policy.complex_residual_risk * error_probability
                    + 0.15 * observation.evidence_conflict,
            ),
        ]);

        let mut ranked: Vec<(StrategyKind, f64)> = input
            .available_strategies
            .iter()
            .map(|strategy| (*strategy, all_scores[strategy]))
            .collect();
        ranked.sort_by(|left, right| left.1.total_cmp(&right.1));

        let selected_strategy = ranked[0].0;
        let alternative_strategies = ranked.iter().skip(1).map(|(kind, _)| *kind).collect();
        let confidence = match ranked.get(1) {
            Some((_, second_score)) => {
                ((second_score - ranked[0].1) / second_score.abs().max(1e-12)).clamp(0.0, 1.0)
            }
            None => 1.0,
        };

        Ok(DecisionResult {
            selected_strategy,
            alternative_strategies,
            decision_reason: format!(
                "minimum expected cost; error_probability={error_probability:.6}, evidence_conflict={:.6}, unsupported_evidence_ratio={:.6}",
                observation.evidence_conflict, observation.unsupported_evidence_ratio
            ),
            strategy_scores: ranked.into_iter().collect(),
            confidence,
        })
    }

    pub fn decide_transition(
        &self,
        input: TransitionDecisionInput<'_>,
    ) -> Result<TransitionDecisionResult, RuntimeError> {
        if input.candidates.is_empty() {
            return Err(RuntimeError::NoAvailableStrategy);
        }

        let mut ranked = input.candidates.to_vec();
        ranked.sort_by(|left, right| {
            left.expected_cost
                .total_cmp(&right.expected_cost)
                .then_with(|| left.relation.cmp(&right.relation))
                .then_with(|| left.target.cmp(&right.target))
        });
        if ranked.len() > 1 && (ranked[1].expected_cost - ranked[0].expected_cost).abs() <= 1e-12 {
            return Err(RuntimeError::TransitionDecisionRequired {
                source: ranked[0].source.clone(),
                candidate_count: ranked.len(),
            });
        }
        let selected_transition = ranked[0].clone();
        let alternative_transitions = ranked.iter().skip(1).cloned().collect::<Vec<_>>();
        let selected_to_next_score_gap = ranked
            .get(1)
            .map(|next| next.expected_cost - selected_transition.expected_cost);
        let transition_scores = ranked
            .iter()
            .map(|candidate| (candidate.id(), candidate.expected_cost))
            .collect();

        Ok(TransitionDecisionResult {
            selected_transition,
            alternative_transitions,
            decision_reason: "minimum expected transition cost".to_string(),
            transition_scores,
            selected_to_next_score_gap,
        })
    }

    pub fn decide_graph_path(
        &self,
        input: GraphDecisionInput<'_>,
    ) -> Result<GraphDecisionResult, RuntimeError> {
        if input.candidates.is_empty() {
            return Err(RuntimeError::GraphPathNotFound {
                start: input.source.to_string(),
                target: "*".to_string(),
            });
        }

        let mut ranked = input.candidates.to_vec();
        ranked.sort_by(|left, right| {
            left.total_cost
                .total_cmp(&right.total_cost)
                .then_with(|| left.id().cmp(&right.id()))
        });
        if ranked.len() > 1 && (ranked[1].total_cost - ranked[0].total_cost).abs() <= 1e-12 {
            return Err(RuntimeError::GraphDecisionRequired {
                source: input.source.to_string(),
                candidate_count: ranked.len(),
            });
        }

        let selected_path = ranked[0].clone();
        let alternative_paths = ranked.iter().skip(1).cloned().collect::<Vec<_>>();
        let selected_to_next_score_gap = ranked
            .get(1)
            .map(|next| next.total_cost - selected_path.total_cost);
        let path_scores = ranked
            .iter()
            .map(|candidate| (candidate.id(), candidate.total_cost))
            .collect();

        Ok(GraphDecisionResult {
            selected_path,
            alternative_paths,
            decision_reason: "minimum expected graph path cost".to_string(),
            path_scores,
            selected_to_next_score_gap,
        })
    }
}
