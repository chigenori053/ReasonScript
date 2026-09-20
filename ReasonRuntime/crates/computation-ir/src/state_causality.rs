use crate::causal::CausalRelation;
pub use crate::reasoning_state::StateTransition;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::time::Instant;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum StateCausalityMode {
    #[default]
    Off,
    Trace,
    Full,
}

impl StateCausalityMode {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "off" => Some(Self::Off),
            "trace" => Some(Self::Trace),
            "full" => Some(Self::Full),
            _ => None,
        }
    }

    pub fn enabled(self) -> bool {
        self != Self::Off
    }
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct StateCausalityMetrics {
    pub state_transition_count: u64,
    pub state_changed_field_count: u64,
    pub state_causality_runtime_ns: u64,
    pub state_causal_relation_count: u64,
    pub state_enablement_count: u64,
    pub state_termination_count: u64,
    pub state_transition_coverage: f64,
    pub state_evidence_coverage: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct StateCausalityTrace {
    pub mode: &'static str,
    pub transitions: Vec<StateTransition>,
    pub relations: Vec<CausalRelation>,
    pub metrics: StateCausalityMetrics,
    pub hashes: BTreeMap<&'static str, String>,
    pub diagnostics: Vec<&'static str>,
}

/// Causal projection of transitions produced by `RuntimeReasoningState`.
/// It owns no reasoning state: it only records transitions and relations.
#[derive(Default)]
pub struct StateCausality {
    mode: StateCausalityMode,
    transitions: Vec<StateTransition>,
    relations: Vec<CausalRelation>,
    runtime_ns: u64,
}

impl StateCausality {
    pub fn set_mode(&mut self, mode: StateCausalityMode) {
        self.mode = mode;
    }

    pub fn enabled(&self) -> bool {
        self.mode.enabled()
    }

    pub(crate) fn transitions(&self) -> &[StateTransition] {
        &self.transitions
    }

    /// Records a transition and, in `full` mode, its `CAUSES_STATE_CHANGE` relation.
    pub fn observe(&mut self, transition: StateTransition) {
        if !self.enabled() {
            return;
        }
        let started = Instant::now();
        if self.mode == StateCausalityMode::Full {
            self.relations.push(state_relation(
                &transition.source_ru,
                &transition.id,
                "CAUSES_STATE_CHANGE",
                &transition,
            ));
        }
        self.transitions.push(transition);
        self.runtime_ns += started.elapsed().as_nanos() as u64;
    }

    pub fn link_next_ru(&mut self, ru_ref: &str, ru_kind: &str) {
        if self.mode != StateCausalityMode::Full {
            return;
        }
        let Some(transition) = self.transitions.last() else {
            return;
        };
        let kind = if transition
            .changed_fields
            .iter()
            .any(|field| field == "goal_status")
            && ru_kind == "TERMINATION_CHECK"
        {
            "TERMINATES"
        } else if enables(&transition.changed_fields, ru_kind) {
            "ENABLES"
        } else {
            return;
        };
        let relation = state_relation(&transition.id, ru_ref, kind, transition);
        self.relations.push(relation);
    }

    pub fn trace(&self, diagnostics: Vec<&'static str>) -> StateCausalityTrace {
        let transition_count = self.transitions.len();
        let with_source = self
            .transitions
            .iter()
            .filter(|transition| !transition.source_ru.is_empty())
            .count();
        let with_evidence = self
            .transitions
            .iter()
            .filter(|transition| !transition.evidence_refs.is_empty())
            .count();
        StateCausalityTrace {
            mode: match self.mode {
                StateCausalityMode::Off => "off",
                StateCausalityMode::Trace => "trace",
                StateCausalityMode::Full => "full",
            },
            transitions: self.transitions.clone(),
            relations: self.relations.clone(),
            metrics: StateCausalityMetrics {
                state_transition_count: transition_count as u64,
                state_changed_field_count: self
                    .transitions
                    .iter()
                    .map(|transition| transition.changed_fields.len() as u64)
                    .sum(),
                state_causality_runtime_ns: self.runtime_ns,
                state_causal_relation_count: self.relations.len() as u64,
                state_enablement_count: self
                    .relations
                    .iter()
                    .filter(|relation| relation.relation_kind == "ENABLES")
                    .count() as u64,
                state_termination_count: self
                    .relations
                    .iter()
                    .filter(|relation| relation.relation_kind == "TERMINATES")
                    .count() as u64,
                state_transition_coverage: ratio(with_source, transition_count),
                state_evidence_coverage: ratio(with_evidence, transition_count),
            },
            hashes: BTreeMap::from([("state_transition_hash", transition_hash(&self.transitions))]),
            diagnostics,
        }
    }
}

fn enables(fields: &[String], kind: &str) -> bool {
    fields.iter().any(|field| match field.as_str() {
        "current_candidate" => kind == "VERIFICATION",
        "remaining" | "search_bound" => {
            matches!(kind, "HYPOTHESIS" | "VERIFICATION" | "GOAL_EVALUATION")
        }
        "active_constraint_count" => kind == "CONSTRAINT_DERIVATION",
        _ => false,
    })
}

fn state_relation(
    source: &str,
    target: &str,
    kind: &'static str,
    transition: &StateTransition,
) -> CausalRelation {
    CausalRelation {
        id: String::new(),
        source_ref: source.to_owned(),
        target_ref: target.to_owned(),
        relation_kind: kind,
        evidence_refs: transition.evidence_refs.clone(),
        dependency: Some(true),
        necessity: None,
        sufficiency: None,
        polarity: "POSITIVE",
        modality: "ACTUAL",
        status: "CONFIRMED",
        provenance: serde_json::json!({
            "evidence_refs": transition.evidence_refs,
            "counterfactual_result_ref": null,
            "observation_source": "native_state",
            "state_revision_before": transition.revision_before,
            "state_revision_after": transition.revision_after,
            "changed_fields": transition.changed_fields,
        }),
    }
}

fn transition_hash(transitions: &[StateTransition]) -> String {
    format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(transitions).unwrap())
    )
}

fn ratio(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        1.0
    } else {
        numerator as f64 / denominator as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::reasoning_state::{
        ReasonStateField as F, ReasonStateValue as V, ReasoningStateMode, RuntimeReasoningState,
    };

    #[test]
    fn projects_state_owned_transitions_and_hashes_deterministically() {
        let run = || {
            let mut state = RuntimeReasoningState::default();
            state.set_mode(ReasoningStateMode::Lightweight);
            state
                .initialize(&[(F::Remaining, V::Int(77)), (F::SearchBound, V::Int(8))])
                .unwrap();
            let mut causality = StateCausality::default();
            causality.set_mode(StateCausalityMode::Full);
            let updates = [(F::Remaining, V::Int(11)), (F::SearchBound, V::Int(3))];
            causality.observe(
                state
                    .apply(
                        Some("ru:verification:1"),
                        &updates,
                        &["evidence:factor:7".to_owned()],
                    )
                    .unwrap(),
            );
            assert!(state
                .apply(Some("ru:verification:1"), &updates, &[])
                .is_none());
            causality.link_next_ru("ru:goal-evaluation:2", "GOAL_EVALUATION");
            causality.trace(state.diagnostics())
        };
        let (first, second) = (run(), run());
        assert_eq!(first.transitions.len(), 1);
        assert_eq!(
            first.transitions[0].changed_fields,
            ["remaining", "search_bound"]
        );
        let kinds: Vec<_> = first.relations.iter().map(|r| r.relation_kind).collect();
        assert_eq!(kinds, ["CAUSES_STATE_CHANGE", "ENABLES"]);
        assert_eq!(first.relations[0].provenance["state_revision_after"], 1);
        assert_eq!(first.hashes, second.hashes);
        assert_eq!(first.metrics.state_transition_coverage, 1.0);
        assert_eq!(first.metrics.state_evidence_coverage, 1.0);
    }

    #[test]
    fn off_mode_records_nothing() {
        let mut state = RuntimeReasoningState::default();
        let transition = state
            .apply(Some("ru:x"), &[(F::CurrentCandidate, V::Int(7))], &[])
            .unwrap();
        let mut causality = StateCausality::default();
        causality.observe(transition);
        assert!(causality.trace(Vec::new()).transitions.is_empty());
    }
}
