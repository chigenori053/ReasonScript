use crate::causal::CausalRelation;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
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

#[derive(Clone, Debug, Serialize)]
pub struct StateTransition {
    pub id: String,
    pub revision_before: u64,
    pub revision_after: u64,
    pub changed_fields: Vec<String>,
    pub before_values: BTreeMap<String, serde_json::Value>,
    pub after_values: BTreeMap<String, serde_json::Value>,
    pub source_ru: String,
    pub evidence_refs: Vec<String>,
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

#[derive(Default)]
pub struct StateCausality {
    mode: StateCausalityMode,
    revision: u64,
    transitions: Vec<StateTransition>,
    relations: Vec<CausalRelation>,
    diagnostics: Vec<&'static str>,
    runtime_ns: u64,
}

impl StateCausality {
    pub fn set_mode(&mut self, mode: StateCausalityMode) {
        self.mode = mode;
    }

    pub fn enabled(&self) -> bool {
        self.mode.enabled()
    }

    pub fn record(
        &mut self,
        source_ru: Option<&str>,
        before: &serde_json::Value,
        after: &serde_json::Value,
        evidence_refs: &[String],
    ) -> Option<String> {
        if !self.enabled() {
            return None;
        }
        let started = Instant::now();
        let (Some(before), Some(after)) = (before.as_object(), after.as_object()) else {
            self.push_diagnostic("STATE-CAUSAL-003");
            return None;
        };
        let Some(source_ru) = source_ru.filter(|value| !value.is_empty()) else {
            self.push_diagnostic("STATE-CAUSAL-001");
            return None;
        };
        let keys: BTreeSet<_> = before.keys().chain(after.keys()).cloned().collect();
        let changed_fields: Vec<_> = keys
            .into_iter()
            .filter(|key| before.get(key) != after.get(key))
            .collect();
        if changed_fields.is_empty() {
            return None;
        }
        let revision_before = self.revision;
        self.revision += 1;
        let id = format!("state-transition:{:08}", self.transitions.len() + 1);
        let select = |values: &serde_json::Map<String, serde_json::Value>| {
            changed_fields
                .iter()
                .map(|key| {
                    (
                        key.clone(),
                        values.get(key).cloned().unwrap_or(serde_json::Value::Null),
                    )
                })
                .collect()
        };
        let mut evidence_refs = evidence_refs.to_vec();
        evidence_refs.sort();
        evidence_refs.dedup();
        let before_values = select(before);
        let after_values = select(after);
        self.transitions.push(StateTransition {
            id: id.clone(),
            revision_before,
            revision_after: self.revision,
            changed_fields,
            before_values,
            after_values,
            source_ru: source_ru.to_owned(),
            evidence_refs: evidence_refs.clone(),
        });
        if self.mode == StateCausalityMode::Full {
            self.relations.push(state_relation(
                source_ru,
                &id,
                "CAUSES_STATE_CHANGE",
                evidence_refs,
                "CONFIRMED",
            ));
        }
        self.runtime_ns += started.elapsed().as_nanos() as u64;
        Some(id)
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
        if self.relations.iter().any(|relation| {
            relation.source_ref == transition.id
                && relation.target_ref == ru_ref
                && relation.relation_kind == kind
        }) {
            return;
        }
        self.relations.push(state_relation(
            &transition.id,
            ru_ref,
            kind,
            transition.evidence_refs.clone(),
            "CONFIRMED",
        ));
    }

    pub fn trace(&self) -> StateCausalityTrace {
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
            diagnostics: self.diagnostics.clone(),
        }
    }

    fn push_diagnostic(&mut self, code: &'static str) {
        if !self.diagnostics.contains(&code) {
            self.diagnostics.push(code);
        }
    }
}

fn enables(fields: &[String], kind: &str) -> bool {
    fields.iter().any(|field| match field.as_str() {
        "current_candidate" => kind == "VERIFICATION",
        "remaining" | "search_bound" => matches!(kind, "HYPOTHESIS" | "VERIFICATION"),
        "active_constraint_count" => kind == "CONSTRAINT_DERIVATION",
        _ => false,
    })
}

fn state_relation(
    source: &str,
    target: &str,
    kind: &'static str,
    evidence_refs: Vec<String>,
    status: &'static str,
) -> CausalRelation {
    CausalRelation {
        id: String::new(),
        source_ref: source.to_owned(),
        target_ref: target.to_owned(),
        relation_kind: kind,
        evidence_refs: evidence_refs.clone(),
        dependency: Some(true),
        necessity: None,
        sufficiency: None,
        polarity: "POSITIVE",
        modality: "ACTUAL",
        status,
        provenance: serde_json::json!({
            "evidence_refs": evidence_refs,
            "counterfactual_result_ref": null,
            "observation_source": "native_state",
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

    #[test]
    fn records_real_diff_ignores_empty_change_and_hashes_deterministically() {
        let run = || {
            let mut state = StateCausality::default();
            state.set_mode(StateCausalityMode::Full);
            assert!(state
                .record(
                    Some("ru:verification:1"),
                    &serde_json::json!({"remaining": 77, "search_bound": 8}),
                    &serde_json::json!({"remaining": 11, "search_bound": 3}),
                    &["evidence:factor:7".to_owned()],
                )
                .is_some());
            assert!(state
                .record(
                    Some("ru:verification:1"),
                    &serde_json::json!({"remaining": 11}),
                    &serde_json::json!({"remaining": 11}),
                    &[],
                )
                .is_none());
            state.trace()
        };
        let first = run();
        let second = run();
        assert_eq!(first.transitions.len(), 1);
        assert_eq!(
            first.transitions[0].changed_fields,
            ["remaining", "search_bound"]
        );
        assert_eq!(first.hashes, second.hashes);
        assert_eq!(first.metrics.state_transition_coverage, 1.0);
    }
}
