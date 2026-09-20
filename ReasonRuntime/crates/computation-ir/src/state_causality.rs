use crate::causal::CausalRelation;
use crate::reason_structure::ExecutableKind;
pub use crate::reasoning_state::StateTransition;
use crate::reasoning_state::{
    transition_hash, ReasonStateField, RefResolver, RuRef, RuntimeStateTransition,
};
use serde::Serialize;
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
    /// Response-construction phase costs (outside `runtime_execution_ns`).
    pub state_transition_materialization_ns: u64,
    pub provenance_materialization_ns: u64,
    pub transition_hash_ns: u64,
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

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum StateRelationKind {
    CausesStateChange,
    Enables,
    Terminates,
}

impl StateRelationKind {
    fn name(self) -> &'static str {
        match self {
            Self::CausesStateChange => "CAUSES_STATE_CHANGE",
            Self::Enables => "ENABLES",
            Self::Terminates => "TERMINATES",
        }
    }
}

/// Runtime form of a state relation: which transition, which RU, and how they
/// relate. `CAUSES_STATE_CHANGE` runs RU → transition; `ENABLES` and
/// `TERMINATES` run transition → RU. IDs and provenance JSON are produced only
/// when the causal trace is built.
#[derive(Clone, Copy, Debug)]
struct RuntimeStateRelation {
    kind: StateRelationKind,
    transition: u32,
    ru: RuRef,
}

/// Causal projection of transitions produced by `RuntimeReasoningState`.
/// It owns no reasoning state: it only records transitions and relations.
#[derive(Default)]
pub struct StateCausality {
    mode: StateCausalityMode,
    /// Keep transitions even while the mode is `off` (RUS projection needs them);
    /// the state causality artifact still reports nothing in that case.
    retain: bool,
    transitions: Vec<RuntimeStateTransition>,
    relations: Vec<RuntimeStateRelation>,
    runtime_ns: u64,
}

impl StateCausality {
    pub fn set_mode(&mut self, mode: StateCausalityMode) {
        self.mode = mode;
    }

    pub fn enabled(&self) -> bool {
        self.mode.enabled()
    }

    pub(crate) fn set_retain(&mut self, retain: bool) {
        self.retain = retain;
    }

    pub(crate) fn transitions(&self) -> &[RuntimeStateTransition] {
        &self.transitions
    }

    /// Records a transition and, in `full` mode, its `CAUSES_STATE_CHANGE` relation.
    pub fn observe(&mut self, transition: RuntimeStateTransition) {
        if !self.enabled() && !self.retain {
            return;
        }
        let started = Instant::now();
        if self.mode == StateCausalityMode::Full {
            self.relations.push(RuntimeStateRelation {
                kind: StateRelationKind::CausesStateChange,
                transition: self.transitions.len() as u32,
                ru: transition.source_ru,
            });
        }
        self.transitions.push(transition);
        self.runtime_ns += started.elapsed().as_nanos() as u64;
    }

    /// Links the latest transition to an RU that starts after it.
    pub fn link_next_ru(&mut self, ru: RuRef, kind: ExecutableKind) {
        if self.mode != StateCausalityMode::Full {
            return;
        }
        let Some(transition) = self.transitions.last() else {
            return;
        };
        let kind = if transition.changed.contains(ReasonStateField::GoalStatus)
            && kind == ExecutableKind::TerminationCheck
        {
            StateRelationKind::Terminates
        } else if transition.changed.0 & reads(kind) != 0 {
            StateRelationKind::Enables
        } else {
            return;
        };
        self.relations.push(RuntimeStateRelation {
            kind,
            transition: self.transitions.len() as u32 - 1,
            ru,
        });
    }

    pub fn trace(
        &self,
        resolver: &dyn RefResolver,
        diagnostics: Vec<&'static str>,
    ) -> StateCausalityTrace {
        // While only retained for RUS projection, the artifact stays empty.
        let reported: &[RuntimeStateTransition] = if self.enabled() {
            &self.transitions
        } else {
            &[]
        };
        let started = Instant::now();
        let transitions: Vec<StateTransition> = reported
            .iter()
            .map(|transition| transition.to_artifact(resolver))
            .collect();
        let state_transition_materialization_ns = started.elapsed().as_nanos() as u64;
        let started = Instant::now();
        let relations: Vec<CausalRelation> = self
            .relations
            .iter()
            .map(|relation| {
                let transition = &transitions[relation.transition as usize];
                let ru = resolver.ru_id(relation.ru);
                let (source, target) = match relation.kind {
                    StateRelationKind::CausesStateChange => (ru, transition.id.as_str()),
                    _ => (transition.id.as_str(), ru),
                };
                state_relation(source, target, relation.kind.name(), transition)
            })
            .collect();
        let provenance_materialization_ns = started.elapsed().as_nanos() as u64;
        let started = Instant::now();
        let state_transition_hash = transition_hash(reported, resolver);
        let transition_hash_ns = started.elapsed().as_nanos() as u64;
        let transition_count = transitions.len();
        let with_source = transitions
            .iter()
            .filter(|transition| !transition.source_ru.is_empty())
            .count();
        let with_evidence = transitions
            .iter()
            .filter(|transition| !transition.evidence_refs.is_empty())
            .count();
        let count_kind = |kind| {
            self.relations
                .iter()
                .filter(|relation| relation.kind == kind)
                .count() as u64
        };
        StateCausalityTrace {
            mode: match self.mode {
                StateCausalityMode::Off => "off",
                StateCausalityMode::Trace => "trace",
                StateCausalityMode::Full => "full",
            },
            metrics: StateCausalityMetrics {
                state_transition_count: transition_count as u64,
                state_changed_field_count: transitions
                    .iter()
                    .map(|transition| transition.changed_fields.len() as u64)
                    .sum(),
                state_causality_runtime_ns: self.runtime_ns,
                state_causal_relation_count: relations.len() as u64,
                state_enablement_count: count_kind(StateRelationKind::Enables),
                state_termination_count: count_kind(StateRelationKind::Terminates),
                state_transition_coverage: ratio(with_source, transition_count),
                state_evidence_coverage: ratio(with_evidence, transition_count),
                state_transition_materialization_ns,
                provenance_materialization_ns,
                transition_hash_ns,
            },
            hashes: BTreeMap::from([("state_transition_hash", state_transition_hash)]),
            transitions,
            relations,
            diagnostics,
        }
    }
}

/// Fields each RU kind reads (the v0.1 semantic mapping): a transition that
/// changes one of them `ENABLES` the next RU of that kind. Goal-status changes
/// instead `TERMINATE` a termination check.
fn reads(kind: ExecutableKind) -> u8 {
    use ReasonStateField as F;
    match kind {
        ExecutableKind::Hypothesis | ExecutableKind::GoalEvaluation => {
            F::Remaining.bit() | F::SearchBound.bit()
        }
        ExecutableKind::Verification => {
            F::Remaining.bit() | F::SearchBound.bit() | F::CurrentCandidate.bit()
        }
        ExecutableKind::ConstraintDerivation => F::ActiveConstraintCount.bit(),
        ExecutableKind::TerminationCheck => 0,
    }
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
    use crate::reasoning_state::tests::TestResolver;
    use crate::reasoning_state::{
        EvidenceRef, ReasonStateField as F, ReasonStateValue as V, ReasoningStateMode,
        RuntimeReasoningState,
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
                    .apply(Some(RuRef(0)), &updates, &[EvidenceRef(0)])
                    .unwrap(),
            );
            assert!(state.apply(Some(RuRef(0)), &updates, &[]).is_none());
            causality.link_next_ru(RuRef(1), ExecutableKind::GoalEvaluation);
            causality.trace(&TestResolver, state.diagnostics())
        };
        let (first, second) = (run(), run());
        assert_eq!(first.transitions.len(), 1);
        assert_eq!(
            first.transitions[0].changed_fields,
            ["remaining", "search_bound"]
        );
        let kinds: Vec<_> = first.relations.iter().map(|r| r.relation_kind).collect();
        assert_eq!(kinds, ["CAUSES_STATE_CHANGE", "ENABLES"]);
        assert_eq!(
            (
                &first.relations[0].source_ref,
                &first.relations[0].target_ref
            ),
            (&"ru:a".to_owned(), &"state-transition:00000001".to_owned())
        );
        assert_eq!(
            (
                &first.relations[1].source_ref,
                &first.relations[1].target_ref
            ),
            (&"state-transition:00000001".to_owned(), &"ru:b".to_owned())
        );
        assert_eq!(first.relations[0].provenance["state_revision_after"], 1);
        assert_eq!(first.relations[0].provenance["state_revision_before"], 0);
        assert_eq!(
            first.relations[0].provenance["changed_fields"],
            serde_json::json!(["remaining", "search_bound"])
        );
        assert_eq!(first.hashes, second.hashes);
        assert_eq!(first.metrics.state_transition_coverage, 1.0);
        assert_eq!(first.metrics.state_evidence_coverage, 1.0);
        assert_eq!(first.metrics.state_enablement_count, 1);
    }

    #[test]
    fn semantic_mapping_and_termination_follow_the_changed_mask() {
        let mut state = RuntimeReasoningState::default();
        state.set_mode(ReasoningStateMode::Lightweight);
        let mut causality = StateCausality::default();
        causality.set_mode(StateCausalityMode::Full);
        let mut step = |updates: &[(F, V)], causality: &mut StateCausality| {
            causality.observe(state.apply(Some(RuRef(0)), updates, &[]).unwrap());
        };
        step(&[(F::CurrentCandidate, V::Int(7))], &mut causality);
        causality.link_next_ru(RuRef(1), ExecutableKind::Verification);
        causality.link_next_ru(RuRef(2), ExecutableKind::Hypothesis);
        step(&[(F::ActiveConstraintCount, V::Int(1))], &mut causality);
        causality.link_next_ru(RuRef(2), ExecutableKind::ConstraintDerivation);
        causality.link_next_ru(RuRef(3), ExecutableKind::GoalEvaluation);
        step(
            &[(
                F::GoalStatus,
                V::Goal(crate::reasoning_state::GoalStatus::Reached),
            )],
            &mut causality,
        );
        causality.link_next_ru(RuRef(3), ExecutableKind::TerminationCheck);
        let relations = causality.trace(&TestResolver, Vec::new()).relations;
        let triples: Vec<_> = relations
            .iter()
            .map(|r| {
                (
                    r.relation_kind,
                    r.source_ref.as_str(),
                    r.target_ref.as_str(),
                )
            })
            .collect();
        assert_eq!(
            triples,
            [
                ("CAUSES_STATE_CHANGE", "ru:a", "state-transition:00000001"),
                ("ENABLES", "state-transition:00000001", "ru:b"),
                ("CAUSES_STATE_CHANGE", "ru:a", "state-transition:00000002"),
                ("ENABLES", "state-transition:00000002", "ru:c"),
                ("CAUSES_STATE_CHANGE", "ru:a", "state-transition:00000003"),
                ("TERMINATES", "state-transition:00000003", "ru:d"),
            ]
        );
    }

    #[test]
    fn off_mode_records_nothing() {
        let mut state = RuntimeReasoningState::default();
        let transition = state
            .apply(Some(RuRef(0)), &[(F::CurrentCandidate, V::Int(7))], &[])
            .unwrap();
        let mut causality = StateCausality::default();
        causality.observe(transition);
        assert!(causality
            .trace(&TestResolver, Vec::new())
            .transitions
            .is_empty());
    }
}
