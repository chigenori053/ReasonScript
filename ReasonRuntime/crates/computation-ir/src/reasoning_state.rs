//! Lightweight Runtime Reasoning State (Lightweight RUS v0.1).
//!
//! `RuntimeReasoningState` is the source of truth for the reasoning fields.
//! Every mutation goes through [`RuntimeReasoningState::apply`], which diffs
//! the update against the stored state, increments the revision once per
//! atomic update, and returns the resulting [`StateTransition`]. Callers never
//! build before/after values.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::time::Instant;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum ReasoningStateMode {
    #[default]
    Off,
    Lightweight,
}

impl ReasoningStateMode {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "off" => Some(Self::Off),
            "lightweight" => Some(Self::Lightweight),
            _ => None,
        }
    }

    pub fn enabled(self) -> bool {
        self != Self::Off
    }
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum ReasonStateField {
    Remaining,
    SearchBound,
    CurrentCandidate,
    ActiveConstraintCount,
    GoalStatus,
}

impl ReasonStateField {
    const ALL: [Self; 5] = [
        Self::Remaining,
        Self::SearchBound,
        Self::CurrentCandidate,
        Self::ActiveConstraintCount,
        Self::GoalStatus,
    ];

    pub fn name(self) -> &'static str {
        match self {
            Self::Remaining => "remaining",
            Self::SearchBound => "search_bound",
            Self::CurrentCandidate => "current_candidate",
            Self::ActiveConstraintCount => "active_constraint_count",
            Self::GoalStatus => "goal_status",
        }
    }

    pub fn parse(name: &str) -> Option<Self> {
        Self::ALL.into_iter().find(|field| field.name() == name)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum GoalStatus {
    Active,
    Reached,
    Failed,
    Insufficient,
}

impl GoalStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Active => "ACTIVE",
            Self::Reached => "REACHED",
            Self::Failed => "FAILED",
            Self::Insufficient => "INSUFFICIENT",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        [
            Self::Active,
            Self::Reached,
            Self::Failed,
            Self::Insufficient,
        ]
        .into_iter()
        .find(|status| status.as_str() == value)
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum ReasonStateValue {
    None,
    Int(i64),
    Bool(bool),
    String(String),
    Json(serde_json::Value),
}

impl ReasonStateValue {
    pub fn from_json(value: &serde_json::Value) -> Self {
        match value {
            serde_json::Value::Null => Self::None,
            serde_json::Value::Bool(value) => Self::Bool(*value),
            serde_json::Value::String(value) => Self::String(value.clone()),
            serde_json::Value::Number(number) => number
                .as_i64()
                .map_or_else(|| Self::Json(value.clone()), Self::Int),
            _ => Self::Json(value.clone()),
        }
    }

    pub fn to_json(&self) -> serde_json::Value {
        match self {
            Self::None => serde_json::Value::Null,
            Self::Int(value) => (*value).into(),
            Self::Bool(value) => (*value).into(),
            Self::String(value) => value.clone().into(),
            Self::Json(value) => value.clone(),
        }
    }

    fn goal(status: GoalStatus) -> Self {
        Self::String(status.as_str().to_owned())
    }

    fn valid_for(&self, field: ReasonStateField) -> bool {
        use ReasonStateField as F;
        match (field, self) {
            (F::CurrentCandidate, _) | (F::Remaining | F::SearchBound, Self::None) => true,
            (F::Remaining | F::SearchBound | F::ActiveConstraintCount, Self::Int(value)) => {
                *value >= 0
            }
            (F::GoalStatus, Self::String(value)) => GoalStatus::parse(value).is_some(),
            _ => false,
        }
    }
}

pub type StateUpdate = (ReasonStateField, ReasonStateValue);

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
pub struct ReasoningStateMetrics {
    pub reasoning_state_revision_count: u64,
    pub reasoning_state_update_count: u64,
    pub reasoning_state_noop_update_count: u64,
    pub reasoning_state_changed_field_count: u64,
    pub reasoning_state_runtime_ns: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct ReasoningStateTrace {
    pub mode: &'static str,
    pub revision: u64,
    pub fields: BTreeMap<&'static str, serde_json::Value>,
    pub hash: String,
    pub initial_hash: String,
    pub metrics: ReasoningStateMetrics,
    pub diagnostics: Vec<&'static str>,
}

/// What a completed Executable RU does to the reasoning state.
pub(crate) enum StateEffect {
    Initialize(Vec<StateUpdate>),
    Update(Vec<StateUpdate>),
}

type Fields = BTreeMap<ReasonStateField, ReasonStateValue>;

#[derive(Clone, Debug)]
pub struct RuntimeReasoningState {
    mode: ReasoningStateMode,
    revision: u64,
    fields: Fields,
    initial_fields: Fields,
    metrics: ReasoningStateMetrics,
    diagnostics: Vec<&'static str>,
}

impl Default for RuntimeReasoningState {
    fn default() -> Self {
        let fields: Fields = ReasonStateField::ALL
            .into_iter()
            .map(|field| {
                let value = match field {
                    ReasonStateField::ActiveConstraintCount => ReasonStateValue::Int(0),
                    ReasonStateField::GoalStatus => ReasonStateValue::goal(GoalStatus::Active),
                    _ => ReasonStateValue::None,
                };
                (field, value)
            })
            .collect();
        Self {
            mode: ReasoningStateMode::Off,
            revision: 0,
            initial_fields: fields.clone(),
            fields,
            metrics: ReasoningStateMetrics::default(),
            diagnostics: Vec::new(),
        }
    }
}

impl RuntimeReasoningState {
    pub fn set_mode(&mut self, mode: ReasoningStateMode) {
        self.mode = mode;
    }

    pub fn enabled(&self) -> bool {
        self.mode.enabled()
    }

    pub fn revision(&self) -> u64 {
        self.revision
    }

    pub fn diagnostics(&self) -> Vec<&'static str> {
        self.diagnostics.clone()
    }

    pub fn remaining(&self) -> Option<i64> {
        match self.fields[&ReasonStateField::Remaining] {
            ReasonStateValue::Int(value) => Some(value),
            _ => None,
        }
    }

    pub fn search_bound(&self) -> Option<i64> {
        match self.fields[&ReasonStateField::SearchBound] {
            ReasonStateValue::Int(value) => Some(value),
            _ => None,
        }
    }

    pub fn current_candidate(&self) -> &ReasonStateValue {
        &self.fields[&ReasonStateField::CurrentCandidate]
    }

    pub fn active_constraint_count(&self) -> i64 {
        match self.fields[&ReasonStateField::ActiveConstraintCount] {
            ReasonStateValue::Int(value) => value,
            _ => 0,
        }
    }

    pub fn goal_status(&self) -> GoalStatus {
        match &self.fields[&ReasonStateField::GoalStatus] {
            ReasonStateValue::String(value) => GoalStatus::parse(value),
            _ => None,
        }
        .unwrap_or(GoalStatus::Active)
    }

    pub(crate) fn diagnose(&mut self, code: &'static str) {
        if !self.diagnostics.contains(&code) {
            self.diagnostics.push(code);
        }
    }

    /// State construction (revision 0). Sets initial values without producing
    /// a transition; refused once any transition has been applied.
    pub fn initialize(&mut self, values: &[StateUpdate]) -> Result<(), &'static str> {
        if self.revision != 0 {
            self.diagnose("RUS-004");
            return Err("RUS-004");
        }
        if values.iter().any(|(field, value)| !value.valid_for(*field)) {
            self.diagnose("RUS-003");
            return Err("RUS-003");
        }
        self.fields.extend(values.iter().cloned());
        self.initial_fields = self.fields.clone();
        Ok(())
    }

    /// Atomic multi-field update: one revision and one transition per call.
    /// No-op updates change nothing and return `None`.
    pub fn apply(
        &mut self,
        source_ru: Option<&str>,
        updates: &[StateUpdate],
        evidence_refs: &[String],
    ) -> Option<StateTransition> {
        let started = Instant::now();
        let transition = self.apply_inner(source_ru, updates, evidence_refs);
        self.metrics.reasoning_state_runtime_ns += started.elapsed().as_nanos() as u64;
        transition
    }

    /// External-artifact entry point: string field names, JSON values.
    pub fn apply_json(
        &mut self,
        source_ru: Option<&str>,
        updates: &serde_json::Map<String, serde_json::Value>,
        evidence_refs: &[String],
    ) -> Option<StateTransition> {
        let mut typed = Vec::with_capacity(updates.len());
        for (name, value) in updates {
            let Some(field) = ReasonStateField::parse(name) else {
                self.diagnose("RUS-002");
                return None;
            };
            typed.push((field, ReasonStateValue::from_json(value)));
        }
        self.apply(source_ru, &typed, evidence_refs)
    }

    fn apply_inner(
        &mut self,
        source_ru: Option<&str>,
        updates: &[StateUpdate],
        evidence_refs: &[String],
    ) -> Option<StateTransition> {
        let Some(source_ru) = source_ru.filter(|source| !source.is_empty()) else {
            self.diagnose("RUS-001");
            return None;
        };
        if updates
            .iter()
            .any(|(field, value)| !value.valid_for(*field))
        {
            self.diagnose("RUS-003");
            return None;
        }
        self.metrics.reasoning_state_update_count += 1;
        // Later entries for the same field win.
        let wanted: BTreeMap<_, _> = updates
            .iter()
            .map(|(field, value)| (*field, value))
            .collect();
        let changed: Vec<_> = wanted
            .into_iter()
            .filter(|(field, value)| self.fields[field] != **value)
            .collect();
        if changed.is_empty() {
            self.metrics.reasoning_state_noop_update_count += 1;
            return None;
        }
        let mut before_values = BTreeMap::new();
        let mut after_values = BTreeMap::new();
        for (field, value) in changed {
            let previous = self.fields.insert(field, value.clone()).unwrap();
            before_values.insert(field.name().to_owned(), previous.to_json());
            after_values.insert(field.name().to_owned(), value.to_json());
        }
        let revision_before = self.revision;
        self.revision += 1;
        self.metrics.reasoning_state_revision_count += 1;
        self.metrics.reasoning_state_changed_field_count += after_values.len() as u64;
        let mut evidence_refs = evidence_refs.to_vec();
        evidence_refs.sort();
        evidence_refs.dedup();
        Some(StateTransition {
            id: format!("state-transition:{:08}", self.revision),
            revision_before,
            revision_after: self.revision,
            changed_fields: after_values.keys().cloned().collect(),
            before_values,
            after_values,
            source_ru: source_ru.to_owned(),
            evidence_refs,
        })
    }

    /// Runtime semantics of a completed Executable RU, keyed by its operation.
    /// `Ok(None)` means the RU does not touch the reasoning state.
    pub(crate) fn effect_of(
        &self,
        operation: &str,
        verified: bool,
        subject: &serde_json::Value,
    ) -> Result<Option<StateEffect>, &'static str> {
        use ReasonStateField as F;
        let update = |updates: Vec<StateUpdate>| Ok(Some(StateEffect::Update(updates)));
        match operation {
            "REASON_STATE_CREATED" => {
                let Some(target) = subject.as_i64().filter(|target| *target >= 0) else {
                    return Err("RUS-003");
                };
                Ok(Some(StateEffect::Initialize(vec![
                    (F::Remaining, ReasonStateValue::Int(target)),
                    (F::SearchBound, ReasonStateValue::Int(target.isqrt())),
                    (F::GoalStatus, ReasonStateValue::goal(GoalStatus::Active)),
                ])))
            }
            "CANDIDATE_ADOPTED" | "HYPOTHESIS_CREATED" | "CANDIDATE_GENERATED" => update(vec![(
                F::CurrentCandidate,
                ReasonStateValue::from_json(subject),
            )]),
            "CANDIDATE_PREDICATE" if verified => update(vec![(
                F::ActiveConstraintCount,
                ReasonStateValue::Int(self.active_constraint_count() + 1),
            )]),
            "EVIDENCE_ADDED" => update(vec![(
                F::ActiveConstraintCount,
                ReasonStateValue::Int(self.active_constraint_count() + 1),
            )]),
            "HYPOTHESIS_VERIFIED" => {
                // Only meaningful once a target has been initialized.
                let Some(remaining) = self.remaining() else {
                    return Ok(None);
                };
                let Some(factor) = subject.as_i64().filter(|factor| *factor > 1) else {
                    return Err("RUS-003");
                };
                if remaining % factor != 0 {
                    return Err("RUS-003");
                }
                let quotient = remaining / factor;
                update(vec![
                    (F::Remaining, ReasonStateValue::Int(quotient)),
                    (F::SearchBound, ReasonStateValue::Int(quotient.isqrt())),
                ])
            }
            "GOAL_UPDATED" | "TERMINATION_INFERRED" | "FILTER_GOAL" => update(vec![(
                F::GoalStatus,
                ReasonStateValue::goal(GoalStatus::Reached),
            )]),
            _ => Ok(None),
        }
    }

    /// Canonical SHA-256 over the revision and the fields in external-name order.
    pub fn hash(&self) -> String {
        state_hash(self.revision, &self.fields)
    }

    pub fn initial_hash(&self) -> String {
        state_hash(0, &self.initial_fields)
    }

    /// The state as constructed, before any transition.
    pub fn initial_state(&self) -> Self {
        Self {
            revision: 0,
            fields: self.initial_fields.clone(),
            metrics: ReasoningStateMetrics::default(),
            diagnostics: Vec::new(),
            ..self.clone()
        }
    }

    /// Rebuilds a state by replaying transitions, verifying revision continuity
    /// (`RUS-004`), field names (`RUS-002`) and before/after values (`RUS-003`).
    pub fn replay(initial: &Self, transitions: &[StateTransition]) -> Result<Self, &'static str> {
        let mut state = initial.clone();
        for transition in transitions {
            if transition.revision_before != state.revision
                || transition.revision_after != transition.revision_before + 1
            {
                return Err("RUS-004");
            }
            let parse = |name: &String| ReasonStateField::parse(name).ok_or("RUS-002");
            for (name, before) in &transition.before_values {
                if state.fields[&parse(name)?].to_json() != *before {
                    return Err("RUS-003");
                }
            }
            for (name, after) in &transition.after_values {
                let field = parse(name)?;
                let value = ReasonStateValue::from_json(after);
                if !value.valid_for(field) {
                    return Err("RUS-003");
                }
                state.fields.insert(field, value);
            }
            state.revision = transition.revision_after;
        }
        Ok(state)
    }

    pub fn trace(&self) -> ReasoningStateTrace {
        ReasoningStateTrace {
            mode: if self.enabled() { "lightweight" } else { "off" },
            revision: self.revision,
            fields: self
                .fields
                .iter()
                .map(|(field, value)| (field.name(), value.to_json()))
                .collect(),
            hash: self.hash(),
            initial_hash: self.initial_hash(),
            metrics: self.metrics.clone(),
            diagnostics: self.diagnostics.clone(),
        }
    }
}

fn state_hash(revision: u64, fields: &Fields) -> String {
    #[derive(Serialize)]
    struct Canonical<'a> {
        revision: u64,
        fields: BTreeMap<&'static str, &'a serde_json::Value>,
    }
    let values: Vec<_> = fields
        .iter()
        .map(|(field, value)| (field.name(), value.to_json()))
        .collect();
    let canonical = Canonical {
        revision,
        fields: values.iter().map(|(name, value)| (*name, value)).collect(),
    };
    format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(&canonical).unwrap())
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use ReasonStateField as F;
    use ReasonStateValue as V;

    fn enabled() -> RuntimeReasoningState {
        let mut state = RuntimeReasoningState::default();
        state.set_mode(ReasoningStateMode::Lightweight);
        state
    }

    fn factorization() -> RuntimeReasoningState {
        let mut state = enabled();
        state
            .initialize(&[(F::Remaining, V::Int(77)), (F::SearchBound, V::Int(8))])
            .unwrap();
        state
    }

    #[test]
    fn group_a_initial_state_is_revision_zero_with_typed_defaults() {
        let state = enabled();
        assert_eq!(state.revision(), 0);
        assert_eq!(state.remaining(), None);
        assert_eq!(state.search_bound(), None);
        assert_eq!(state.current_candidate(), &V::None);
        assert_eq!(state.active_constraint_count(), 0);
        assert_eq!(state.goal_status(), GoalStatus::Active);
        let state = factorization();
        assert_eq!(
            (state.revision(), state.remaining(), state.search_bound()),
            (0, Some(77), Some(8))
        );
        assert_eq!(state.trace().metrics.reasoning_state_update_count, 0);
    }

    #[test]
    fn group_b_single_field_update_bumps_revision_and_diffs_itself() {
        let mut state = factorization();
        let transition = state
            .apply(
                Some("ru:hypothesis:00000001"),
                &[(F::CurrentCandidate, V::Int(7))],
                &[],
            )
            .unwrap();
        assert_eq!(
            (transition.revision_before, transition.revision_after),
            (0, 1)
        );
        assert_eq!(transition.changed_fields, ["current_candidate"]);
        assert_eq!(
            transition.before_values["current_candidate"],
            serde_json::Value::Null
        );
        assert_eq!(transition.after_values["current_candidate"], 7);
        assert_eq!(transition.id, "state-transition:00000001");
    }

    #[test]
    fn group_c_multi_field_update_is_one_atomic_transition() {
        let mut state = factorization();
        let transition = state
            .apply(
                Some("ru:verification:00000002"),
                &[(F::SearchBound, V::Int(3)), (F::Remaining, V::Int(11))],
                &[
                    "evidence:ru:00000002".to_owned(),
                    "evidence:ru:00000002".to_owned(),
                ],
            )
            .unwrap();
        assert_eq!(transition.changed_fields, ["remaining", "search_bound"]);
        assert_eq!(
            (transition.revision_before, transition.revision_after),
            (0, 1)
        );
        assert_eq!(transition.before_values["remaining"], 77);
        assert_eq!(transition.after_values["search_bound"], 3);
        assert_eq!(transition.evidence_refs, ["evidence:ru:00000002"]);
        assert_eq!(state.revision(), 1);
        assert_eq!(state.trace().metrics.reasoning_state_changed_field_count, 2);
    }

    #[test]
    fn group_d_noop_update_creates_neither_revision_nor_transition() {
        let mut state = factorization();
        let source = Some("ru:verification:00000002");
        assert!(state
            .apply(source, &[(F::Remaining, V::Int(77))], &[])
            .is_none());
        assert_eq!(state.revision(), 0);
        let metrics = state.trace().metrics;
        assert_eq!(
            (
                metrics.reasoning_state_update_count,
                metrics.reasoning_state_noop_update_count
            ),
            (1, 1)
        );
        assert!(state.trace().diagnostics.is_empty());
    }

    #[test]
    fn diagnostics_cover_missing_source_field_value_and_revision() {
        let mut state = factorization();
        assert!(state
            .apply(None, &[(F::Remaining, V::Int(11))], &[])
            .is_none());
        assert!(state
            .apply(Some(""), &[(F::Remaining, V::Int(11))], &[])
            .is_none());
        assert!(state
            .apply(Some("ru:x"), &[(F::Remaining, V::Int(-1))], &[])
            .is_none());
        assert!(state
            .apply(
                Some("ru:x"),
                &[(F::GoalStatus, V::String("DONE".into()))],
                &[]
            )
            .is_none());
        let unknown = serde_json::json!({"not_a_field": 1});
        assert!(state
            .apply_json(Some("ru:x"), unknown.as_object().unwrap(), &[])
            .is_none());
        assert_eq!(state.revision(), 0, "rejected updates must not mutate");
        state
            .apply(Some("ru:x"), &[(F::CurrentCandidate, V::Int(7))], &[])
            .unwrap();
        assert_eq!(
            state.initialize(&[(F::Remaining, V::Int(5))]),
            Err("RUS-004")
        );
        assert_eq!(
            state.diagnostics(),
            ["RUS-001", "RUS-003", "RUS-002", "RUS-004"]
        );
        let mut json = serde_json::Map::new();
        json.insert("goal_status".into(), "REACHED".into());
        assert!(state.apply_json(Some("ru:y"), &json, &[]).is_some());
        assert_eq!(state.goal_status(), GoalStatus::Reached);
    }

    #[test]
    fn replay_reconstructs_final_state_and_rejects_broken_revisions() {
        let mut state = factorization();
        let transitions: Vec<_> = [
            vec![(F::CurrentCandidate, V::Int(7))],
            vec![(F::Remaining, V::Int(11)), (F::SearchBound, V::Int(3))],
            vec![(F::GoalStatus, V::String("REACHED".into()))],
        ]
        .iter()
        .map(|updates| state.apply(Some("ru:x"), updates, &[]).unwrap())
        .collect();
        let replayed = RuntimeReasoningState::replay(&state.initial_state(), &transitions).unwrap();
        assert_eq!(replayed.hash(), state.hash());
        assert_eq!(replayed.revision(), 3);
        assert_eq!(
            RuntimeReasoningState::replay(&state.initial_state(), &transitions[1..]).unwrap_err(),
            "RUS-004"
        );
    }

    #[test]
    fn hash_is_deterministic_and_depends_on_revision_and_values() {
        let run = |remaining| {
            let mut state = factorization();
            state.apply(Some("ru:x"), &[(F::Remaining, V::Int(remaining))], &[]);
            state
        };
        assert_eq!(run(11).hash(), run(11).hash());
        assert_ne!(run(11).hash(), run(7).hash());
        assert_ne!(run(11).hash(), run(11).initial_hash());
        assert_eq!(run(11).initial_hash(), run(7).initial_hash());
    }

    #[test]
    fn effects_derive_remaining_and_bound_from_the_state_not_the_caller() {
        let state = factorization();
        let effect =
            |state: &RuntimeReasoningState, operation, subject: serde_json::Value| match state
                .effect_of(operation, true, &subject)
            {
                Ok(Some(StateEffect::Update(updates))) => Ok(Some(updates)),
                Ok(Some(StateEffect::Initialize(_))) => panic!("unexpected init"),
                Ok(None) => Ok(None),
                Err(code) => Err(code),
            };
        assert_eq!(
            effect(&state, "HYPOTHESIS_VERIFIED", serde_json::json!(7))
                .unwrap()
                .unwrap(),
            vec![(F::Remaining, V::Int(11)), (F::SearchBound, V::Int(3))]
        );
        assert_eq!(
            effect(&state, "HYPOTHESIS_VERIFIED", serde_json::json!(5)),
            Err("RUS-003")
        );
        assert_eq!(
            effect(&state, "HYPOTHESIS_VERIFIED", serde_json::json!(1)),
            Err("RUS-003")
        );
        assert_eq!(
            effect(&enabled(), "HYPOTHESIS_VERIFIED", serde_json::json!(7)),
            Ok(None)
        );
        assert_eq!(
            effect(&state, "HYPOTHESIS_REJECTED", serde_json::json!(7)),
            Ok(None)
        );
        let rejected = state.effect_of(
            "CANDIDATE_PREDICATE",
            false,
            &serde_json::json!({"value": 7}),
        );
        assert!(matches!(rejected, Ok(None)));
    }
}
