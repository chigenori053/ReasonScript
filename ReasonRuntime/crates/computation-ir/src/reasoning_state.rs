//! Lightweight Runtime Reasoning State (Lightweight RUS v0.1).
//!
//! `RuntimeReasoningState` is the source of truth for the reasoning fields.
//! Every mutation goes through [`RuntimeReasoningState::apply`], which diffs
//! the update against the stored state, increments the revision once per
//! atomic update, and returns the resulting [`RuntimeStateTransition`]. Callers
//! never build before/after values.
//!
//! The runtime representation is typed and allocation-free for scalar values:
//! fields are a fixed enum, changes are a bitmask, and RU / Evidence are
//! referenced by index. Field-name strings, JSON values, and canonical IDs are
//! produced only when an artifact is materialized ([`RuntimeStateTransition::to_artifact`]).

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::rc::Rc;
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

/// The five reasoning fields. The discriminant is the bit position in a
/// [`FieldMask`] and the index into the state's value array.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReasonStateField {
    Remaining = 0,
    SearchBound = 1,
    CurrentCandidate = 2,
    ActiveConstraintCount = 3,
    GoalStatus = 4,
}

impl ReasonStateField {
    pub const COUNT: usize = 5;
    /// External-name (alphabetical) order: the order of artifacts and of the
    /// canonical hash bytes.
    pub const BY_NAME: [Self; 5] = [
        Self::ActiveConstraintCount,
        Self::CurrentCandidate,
        Self::GoalStatus,
        Self::Remaining,
        Self::SearchBound,
    ];

    pub fn index(self) -> usize {
        self as usize
    }

    pub fn bit(self) -> u8 {
        1 << (self as u8)
    }

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
        Self::BY_NAME.into_iter().find(|field| field.name() == name)
    }
}

/// Set of changed fields (bit `n` = the field with discriminant `n`).
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct FieldMask(pub u8);

impl FieldMask {
    pub fn contains(self, field: ReasonStateField) -> bool {
        self.0 & field.bit() != 0
    }

    pub fn is_empty(self) -> bool {
        self.0 == 0
    }

    pub fn count(self) -> u64 {
        u64::from(self.0.count_ones())
    }

    /// Changed fields in external-name order.
    pub fn by_name(self) -> impl Iterator<Item = ReasonStateField> {
        ReasonStateField::BY_NAME
            .into_iter()
            .filter(move |field| self.contains(*field))
    }
}

/// Index of an Executable RU in the runtime's unit table.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct RuRef(pub u32);

/// Index of an Evidence record in the runtime's evidence table.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct EvidenceRef(pub u32);

/// Resolves references to their canonical IDs when an artifact is materialized.
pub trait RefResolver {
    fn ru_id(&self, ru: RuRef) -> &str;
    fn evidence_id(&self, evidence: EvidenceRef) -> &str;
}

/// Sorted, de-duplicated Evidence references; inline for the common 0/1 case.
#[derive(Clone, Debug, Default, PartialEq)]
pub enum EvidenceRefs {
    #[default]
    None,
    One(EvidenceRef),
    Many(Vec<EvidenceRef>),
}

impl EvidenceRefs {
    fn from_slice(refs: &[EvidenceRef]) -> Self {
        match refs {
            [] => Self::None,
            [one] => Self::One(*one),
            many => {
                let mut sorted = many.to_vec();
                sorted.sort();
                sorted.dedup();
                match sorted.as_slice() {
                    [one] => Self::One(*one),
                    _ => Self::Many(sorted),
                }
            }
        }
    }

    pub fn as_slice(&self) -> &[EvidenceRef] {
        match self {
            Self::None => &[],
            Self::One(one) => std::slice::from_ref(one),
            Self::Many(many) => many,
        }
    }

    pub fn is_empty(&self) -> bool {
        matches!(self, Self::None)
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

#[derive(Clone, Debug, Default, PartialEq)]
pub enum ReasonStateValue {
    #[default]
    None,
    Int(i64),
    Bool(bool),
    Goal(GoalStatus),
    String(String),
    /// Shared so the state, the transition, and the artifact hold one copy.
    Json(Rc<serde_json::Value>),
}

impl ReasonStateValue {
    pub fn from_json(value: &serde_json::Value) -> Self {
        match value {
            serde_json::Value::Null => Self::None,
            serde_json::Value::Bool(value) => Self::Bool(*value),
            serde_json::Value::String(value) => Self::String(value.clone()),
            serde_json::Value::Number(number) => number
                .as_i64()
                .map_or_else(|| Self::Json(Rc::new(value.clone())), Self::Int),
            _ => Self::Json(Rc::new(value.clone())),
        }
    }

    /// JSON boundary: `goal_status` arrives as its external string name.
    pub fn from_json_for(
        field: ReasonStateField,
        value: &serde_json::Value,
    ) -> Result<Self, &'static str> {
        match (field, value) {
            (ReasonStateField::GoalStatus, serde_json::Value::String(name)) => {
                GoalStatus::parse(name).map(Self::Goal).ok_or("RUS-003")
            }
            _ => Ok(Self::from_json(value)),
        }
    }

    pub fn to_json(&self) -> serde_json::Value {
        match self {
            Self::None => serde_json::Value::Null,
            Self::Int(value) => (*value).into(),
            Self::Bool(value) => (*value).into(),
            Self::Goal(status) => status.as_str().into(),
            Self::String(value) => value.clone().into(),
            Self::Json(value) => (**value).clone(),
        }
    }

    fn valid_for(&self, field: ReasonStateField) -> bool {
        use ReasonStateField as F;
        match (field, self) {
            (F::CurrentCandidate, _) | (F::Remaining | F::SearchBound, Self::None) => true,
            (F::Remaining | F::SearchBound | F::ActiveConstraintCount, Self::Int(value)) => {
                *value >= 0
            }
            (F::GoalStatus, Self::Goal(_)) => true,
            _ => false,
        }
    }
}

impl Serialize for ReasonStateValue {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match self {
            Self::None => serializer.serialize_none(),
            Self::Int(value) => serializer.serialize_i64(*value),
            Self::Bool(value) => serializer.serialize_bool(*value),
            Self::Goal(status) => serializer.serialize_str(status.as_str()),
            Self::String(value) => serializer.serialize_str(value),
            Self::Json(value) => value.serialize(serializer),
        }
    }
}

/// The five fields serialized as a JSON object in external-name order, without
/// building a map.
#[derive(Clone, Debug)]
pub struct FieldsView(pub(crate) Fields);

impl Serialize for FieldsView {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        use serde::ser::SerializeMap;
        let mut map = serializer.serialize_map(Some(ReasonStateField::COUNT))?;
        for field in ReasonStateField::BY_NAME {
            map.serialize_entry(field.name(), &self.0[field.index()])?;
        }
        map.end()
    }
}

pub type StateUpdate = (ReasonStateField, ReasonStateValue);

/// Public artifact form of a transition (the `state_transition` schema).
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

/// Runtime form of a transition: fixed arrays, a change bitmask, and indices.
#[derive(Clone, Debug)]
pub struct RuntimeStateTransition {
    pub revision_before: u64,
    pub source_ru: RuRef,
    pub evidence: EvidenceRefs,
    pub changed: FieldMask,
    before: [ReasonStateValue; ReasonStateField::COUNT],
    after: [ReasonStateValue; ReasonStateField::COUNT],
}

impl RuntimeStateTransition {
    pub fn revision_after(&self) -> u64 {
        self.revision_before + 1
    }

    pub fn before(&self, field: ReasonStateField) -> &ReasonStateValue {
        &self.before[field.index()]
    }

    pub fn after(&self, field: ReasonStateField) -> &ReasonStateValue {
        &self.after[field.index()]
    }

    /// `state-transition:{revision_after:08}`.
    pub fn id(&self) -> String {
        format!("state-transition:{:08}", self.revision_after())
    }

    pub fn to_artifact(&self, resolver: &dyn RefResolver) -> StateTransition {
        let mut changed_fields = Vec::with_capacity(self.changed.0.count_ones() as usize);
        let mut before_values = BTreeMap::new();
        let mut after_values = BTreeMap::new();
        for field in self.changed.by_name() {
            changed_fields.push(field.name().to_owned());
            before_values.insert(field.name().to_owned(), self.before(field).to_json());
            after_values.insert(field.name().to_owned(), self.after(field).to_json());
        }
        let mut evidence_refs: Vec<String> = self
            .evidence
            .as_slice()
            .iter()
            .map(|evidence| resolver.evidence_id(*evidence).to_owned())
            .collect();
        evidence_refs.sort();
        StateTransition {
            id: self.id(),
            revision_before: self.revision_before,
            revision_after: self.revision_after(),
            changed_fields,
            before_values,
            after_values,
            source_ru: resolver.ru_id(self.source_ru).to_owned(),
            evidence_refs,
        }
    }
}

/// Canonical JSON bytes, written without building a `serde_json::Value` tree.
/// They must equal `serde_json::to_vec` of the artifact form byte for byte;
/// tests compare both paths.
fn push_u64(buf: &mut Vec<u8>, mut value: u64, min_width: usize) {
    let mut digits = [0_u8; 20];
    let mut cursor = digits.len();
    loop {
        cursor -= 1;
        digits[cursor] = b'0' + (value % 10) as u8;
        value /= 10;
        if value == 0 {
            break;
        }
    }
    buf.resize(
        buf.len() + min_width.saturating_sub(digits.len() - cursor),
        b'0',
    );
    buf.extend_from_slice(&digits[cursor..]);
}

fn push_json_str(buf: &mut Vec<u8>, value: &str) {
    serde_json::to_writer(&mut *buf, value).expect("writing to a Vec cannot fail");
}

impl ReasonStateValue {
    fn write_json(&self, buf: &mut Vec<u8>) {
        match self {
            Self::None => buf.extend_from_slice(b"null"),
            Self::Int(value) => {
                if *value < 0 {
                    buf.push(b'-');
                }
                push_u64(buf, value.unsigned_abs(), 0);
            }
            Self::Bool(true) => buf.extend_from_slice(b"true"),
            Self::Bool(false) => buf.extend_from_slice(b"false"),
            Self::Goal(status) => {
                buf.push(b'"');
                buf.extend_from_slice(status.as_str().as_bytes());
                buf.push(b'"');
            }
            Self::String(value) => push_json_str(buf, value),
            Self::Json(value) => {
                serde_json::to_writer(&mut *buf, &**value).expect("writing to a Vec cannot fail")
            }
        }
    }
}

impl RuntimeStateTransition {
    /// Canonical bytes of `serde_json::to_vec(&self.to_artifact(resolver))`.
    pub fn write_canonical(&self, buf: &mut Vec<u8>, resolver: &dyn RefResolver) {
        let write_values = |buf: &mut Vec<u8>, values: &Fields| {
            for (position, field) in self.changed.by_name().enumerate() {
                if position > 0 {
                    buf.push(b',');
                }
                buf.push(b'"');
                buf.extend_from_slice(field.name().as_bytes());
                buf.extend_from_slice(b"\":");
                values[field.index()].write_json(buf);
            }
        };
        buf.extend_from_slice(b"{\"id\":\"state-transition:");
        push_u64(buf, self.revision_after(), 8);
        buf.extend_from_slice(b"\",\"revision_before\":");
        push_u64(buf, self.revision_before, 0);
        buf.extend_from_slice(b",\"revision_after\":");
        push_u64(buf, self.revision_after(), 0);
        buf.extend_from_slice(b",\"changed_fields\":[");
        for (position, field) in self.changed.by_name().enumerate() {
            if position > 0 {
                buf.push(b',');
            }
            buf.push(b'"');
            buf.extend_from_slice(field.name().as_bytes());
            buf.push(b'"');
        }
        buf.extend_from_slice(b"],\"before_values\":{");
        write_values(buf, &self.before);
        buf.extend_from_slice(b"},\"after_values\":{");
        write_values(buf, &self.after);
        buf.extend_from_slice(b"},\"source_ru\":");
        push_json_str(buf, resolver.ru_id(self.source_ru));
        buf.extend_from_slice(b",\"evidence_refs\":[");
        let mut ids: Vec<&str> = self
            .evidence
            .as_slice()
            .iter()
            .map(|evidence| resolver.evidence_id(*evidence))
            .collect();
        ids.sort_unstable();
        for (position, id) in ids.into_iter().enumerate() {
            if position > 0 {
                buf.push(b',');
            }
            push_json_str(buf, id);
        }
        buf.extend_from_slice(b"]}");
    }
}

/// SHA-256 of `serde_json::to_vec(&[StateTransition])`, streamed from typed data.
pub fn transition_hash(
    transitions: &[RuntimeStateTransition],
    resolver: &dyn RefResolver,
) -> String {
    let mut hasher = Sha256::new();
    let mut buf = Vec::with_capacity(512);
    hasher.update(b"[");
    for (position, transition) in transitions.iter().enumerate() {
        buf.clear();
        if position > 0 {
            buf.push(b',');
        }
        transition.write_canonical(&mut buf, resolver);
        hasher.update(&buf);
    }
    hasher.update(b"]");
    format!("sha256:{:x}", hasher.finalize())
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct ReasoningStateMetrics {
    pub reasoning_state_revision_count: u64,
    pub reasoning_state_update_count: u64,
    pub reasoning_state_noop_update_count: u64,
    pub reasoning_state_changed_field_count: u64,
    pub reasoning_state_runtime_ns: u64,
    /// Response-construction phase cost of the state hashes.
    pub state_hash_ns: u64,
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
    Initialize([StateUpdate; 3]),
    Update1([StateUpdate; 1]),
    Update2([StateUpdate; 2]),
}

pub(crate) type Fields = [ReasonStateValue; ReasonStateField::COUNT];

#[derive(Clone, Debug)]
pub struct RuntimeReasoningState {
    mode: ReasoningStateMode,
    revision: u64,
    fields: Fields,
    initial_fields: Fields,
    /// The RU that constructed the initial state, if any (revision 0).
    initial_source_ru: Option<RuRef>,
    metrics: ReasoningStateMetrics,
    diagnostics: Vec<&'static str>,
}

impl Default for RuntimeReasoningState {
    fn default() -> Self {
        let mut fields = Fields::default();
        fields[ReasonStateField::ActiveConstraintCount.index()] = ReasonStateValue::Int(0);
        fields[ReasonStateField::GoalStatus.index()] = ReasonStateValue::Goal(GoalStatus::Active);
        Self {
            mode: ReasoningStateMode::Off,
            revision: 0,
            initial_fields: fields.clone(),
            fields,
            initial_source_ru: None,
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
        match self.fields[ReasonStateField::Remaining.index()] {
            ReasonStateValue::Int(value) => Some(value),
            _ => None,
        }
    }

    pub fn search_bound(&self) -> Option<i64> {
        match self.fields[ReasonStateField::SearchBound.index()] {
            ReasonStateValue::Int(value) => Some(value),
            _ => None,
        }
    }

    pub fn current_candidate(&self) -> &ReasonStateValue {
        &self.fields[ReasonStateField::CurrentCandidate.index()]
    }

    pub fn active_constraint_count(&self) -> i64 {
        match self.fields[ReasonStateField::ActiveConstraintCount.index()] {
            ReasonStateValue::Int(value) => value,
            _ => 0,
        }
    }

    pub fn goal_status(&self) -> GoalStatus {
        match self.fields[ReasonStateField::GoalStatus.index()] {
            ReasonStateValue::Goal(status) => status,
            _ => GoalStatus::Active,
        }
    }

    pub(crate) fn initial_fields(&self) -> &Fields {
        &self.initial_fields
    }

    pub(crate) fn initial_source_ru(&self) -> Option<RuRef> {
        self.initial_source_ru
    }

    pub(crate) fn set_initial_source_ru(&mut self, source: RuRef) {
        self.initial_source_ru = Some(source);
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
        for (field, value) in values {
            self.fields[field.index()] = value.clone();
        }
        self.initial_fields = self.fields.clone();
        Ok(())
    }

    /// Atomic multi-field update: one revision and one transition per call.
    /// No-op updates change nothing and return `None`.
    pub fn apply(
        &mut self,
        source_ru: Option<RuRef>,
        updates: &[StateUpdate],
        evidence: &[EvidenceRef],
    ) -> Option<RuntimeStateTransition> {
        let started = Instant::now();
        let transition = self.apply_inner(source_ru, updates, evidence);
        self.metrics.reasoning_state_runtime_ns += started.elapsed().as_nanos() as u64;
        transition
    }

    /// External-artifact entry point: string field names, JSON values.
    pub fn apply_json(
        &mut self,
        source_ru: Option<RuRef>,
        updates: &serde_json::Map<String, serde_json::Value>,
        evidence: &[EvidenceRef],
    ) -> Option<RuntimeStateTransition> {
        let mut typed = Vec::with_capacity(updates.len());
        for (name, value) in updates {
            let Some(field) = ReasonStateField::parse(name) else {
                self.diagnose("RUS-002");
                return None;
            };
            match ReasonStateValue::from_json_for(field, value) {
                Ok(value) => typed.push((field, value)),
                Err(code) => {
                    self.diagnose(code);
                    return None;
                }
            }
        }
        self.apply(source_ru, &typed, evidence)
    }

    fn apply_inner(
        &mut self,
        source_ru: Option<RuRef>,
        updates: &[StateUpdate],
        evidence: &[EvidenceRef],
    ) -> Option<RuntimeStateTransition> {
        let Some(source_ru) = source_ru else {
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
        let mut wanted: [Option<&ReasonStateValue>; ReasonStateField::COUNT] =
            [None; ReasonStateField::COUNT];
        for (field, value) in updates {
            wanted[field.index()] = Some(value);
        }
        let mut changed = FieldMask::default();
        for (index, value) in wanted.iter().enumerate() {
            if value.is_some_and(|value| self.fields[index] != *value) {
                changed.0 |= 1 << index;
            }
        }
        if changed.is_empty() {
            self.metrics.reasoning_state_noop_update_count += 1;
            return None;
        }
        let mut before = Fields::default();
        let mut after = Fields::default();
        for (index, value) in wanted.iter().enumerate() {
            if changed.0 & (1 << index) != 0 {
                let value = value.expect("changed fields have a wanted value");
                before[index] = std::mem::replace(&mut self.fields[index], value.clone());
                after[index] = value.clone();
            }
        }
        let revision_before = self.revision;
        self.revision += 1;
        self.metrics.reasoning_state_revision_count += 1;
        self.metrics.reasoning_state_changed_field_count += changed.count();
        Some(RuntimeStateTransition {
            revision_before,
            source_ru,
            evidence: EvidenceRefs::from_slice(evidence),
            changed,
            before,
            after,
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
        use ReasonStateValue as V;
        let increment = || {
            Ok(Some(StateEffect::Update1([(
                F::ActiveConstraintCount,
                V::Int(self.active_constraint_count() + 1),
            )])))
        };
        match operation {
            "REASON_STATE_CREATED" => {
                let Some(target) = subject.as_i64().filter(|target| *target >= 0) else {
                    return Err("RUS-003");
                };
                Ok(Some(StateEffect::Initialize([
                    (F::Remaining, V::Int(target)),
                    (F::SearchBound, V::Int(target.isqrt())),
                    (F::GoalStatus, V::Goal(GoalStatus::Active)),
                ])))
            }
            "CANDIDATE_ADOPTED" | "HYPOTHESIS_CREATED" | "CANDIDATE_GENERATED" => Ok(Some(
                StateEffect::Update1([(F::CurrentCandidate, V::from_json(subject))]),
            )),
            "CANDIDATE_PREDICATE" if verified => increment(),
            "EVIDENCE_ADDED" => increment(),
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
                Ok(Some(StateEffect::Update2([
                    (F::Remaining, V::Int(quotient)),
                    (F::SearchBound, V::Int(quotient.isqrt())),
                ])))
            }
            "GOAL_UPDATED" | "TERMINATION_INFERRED" | "FILTER_GOAL" => Ok(Some(
                StateEffect::Update1([(F::GoalStatus, V::Goal(GoalStatus::Reached))]),
            )),
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
    /// (`RUS-004`) and before values (`RUS-003`).
    pub fn replay(
        initial: &Self,
        transitions: &[RuntimeStateTransition],
    ) -> Result<Self, &'static str> {
        let mut state = initial.clone();
        for transition in transitions {
            if transition.revision_before != state.revision {
                return Err("RUS-004");
            }
            for field in transition.changed.by_name() {
                if state.fields[field.index()] != *transition.before(field) {
                    return Err("RUS-003");
                }
            }
            for field in transition.changed.by_name() {
                let value = transition.after(field);
                if !value.valid_for(field) {
                    return Err("RUS-003");
                }
                state.fields[field.index()] = value.clone();
            }
            state.revision = transition.revision_after();
        }
        Ok(state)
    }

    pub fn trace(&self) -> ReasoningStateTrace {
        let started = Instant::now();
        let (hash, initial_hash) = (self.hash(), self.initial_hash());
        let mut metrics = self.metrics.clone();
        metrics.state_hash_ns = started.elapsed().as_nanos() as u64;
        ReasoningStateTrace {
            mode: if self.enabled() { "lightweight" } else { "off" },
            revision: self.revision,
            fields: ReasonStateField::BY_NAME
                .into_iter()
                .map(|field| (field.name(), self.fields[field.index()].to_json()))
                .collect(),
            hash,
            initial_hash,
            metrics,
            diagnostics: self.diagnostics.clone(),
        }
    }
}

/// Applies a transition's after values to a field array (RUS projection replay).
pub(crate) fn apply_after(fields: &mut Fields, transition: &RuntimeStateTransition) {
    for field in transition.changed.by_name() {
        fields[field.index()] = transition.after(field).clone();
    }
}

/// `{"revision":R,"fields":{...}}` with fields in external-name order.
pub(crate) fn state_hash(revision: u64, fields: &Fields) -> String {
    let mut buf = Vec::with_capacity(160);
    buf.extend_from_slice(b"{\"revision\":");
    push_u64(&mut buf, revision, 0);
    buf.extend_from_slice(b",\"fields\":{");
    for (position, field) in ReasonStateField::BY_NAME.into_iter().enumerate() {
        if position > 0 {
            buf.push(b',');
        }
        buf.push(b'"');
        buf.extend_from_slice(field.name().as_bytes());
        buf.extend_from_slice(b"\":");
        fields[field.index()].write_json(&mut buf);
    }
    buf.extend_from_slice(b"}}");
    format!("sha256:{:x}", Sha256::digest(&buf))
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use ReasonStateField as F;
    use ReasonStateValue as V;

    /// Fixed IDs for tests that do not run a VM.
    pub(crate) struct TestResolver;

    impl RefResolver for TestResolver {
        fn ru_id(&self, ru: RuRef) -> &str {
            ["ru:a", "ru:b", "ru:c", "ru:d"][ru.0 as usize]
        }

        fn evidence_id(&self, evidence: EvidenceRef) -> &str {
            ["evidence:a", "evidence:b", "evidence:c", "evidence:d"][evidence.0 as usize]
        }
    }

    const RU: Option<RuRef> = Some(RuRef(0));

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
            .apply(RU, &[(F::CurrentCandidate, V::Int(7))], &[])
            .unwrap();
        assert_eq!(transition.changed, FieldMask(F::CurrentCandidate.bit()));
        let artifact = transition.to_artifact(&TestResolver);
        assert_eq!((artifact.revision_before, artifact.revision_after), (0, 1));
        assert_eq!(artifact.changed_fields, ["current_candidate"]);
        assert_eq!(
            artifact.before_values["current_candidate"],
            serde_json::Value::Null
        );
        assert_eq!(artifact.after_values["current_candidate"], 7);
        assert_eq!(artifact.id, "state-transition:00000001");
        assert_eq!(artifact.source_ru, "ru:a");
    }

    #[test]
    fn group_c_multi_field_update_is_one_atomic_transition() {
        let mut state = factorization();
        let transition = state
            .apply(
                Some(RuRef(1)),
                &[(F::SearchBound, V::Int(3)), (F::Remaining, V::Int(11))],
                &[EvidenceRef(1), EvidenceRef(1)],
            )
            .unwrap();
        assert_eq!(
            transition.changed,
            FieldMask(F::Remaining.bit() | F::SearchBound.bit())
        );
        let artifact = transition.to_artifact(&TestResolver);
        assert_eq!(artifact.changed_fields, ["remaining", "search_bound"]);
        assert_eq!((artifact.revision_before, artifact.revision_after), (0, 1));
        assert_eq!(artifact.before_values["remaining"], 77);
        assert_eq!(artifact.after_values["search_bound"], 3);
        assert_eq!(artifact.evidence_refs, ["evidence:b"]);
        assert_eq!(state.revision(), 1);
        assert_eq!(state.trace().metrics.reasoning_state_changed_field_count, 2);
    }

    #[test]
    fn group_d_noop_update_creates_neither_revision_nor_transition() {
        let mut state = factorization();
        assert!(state
            .apply(RU, &[(F::Remaining, V::Int(77))], &[])
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
    fn evidence_refs_are_sorted_deduplicated_and_resolved_by_name() {
        let mut state = factorization();
        let refs = [EvidenceRef(2), EvidenceRef(0), EvidenceRef(2)];
        let transition = state
            .apply(RU, &[(F::CurrentCandidate, V::Int(7))], &refs)
            .unwrap();
        assert_eq!(
            transition.evidence.as_slice(),
            [EvidenceRef(0), EvidenceRef(2)]
        );
        assert_eq!(
            transition.to_artifact(&TestResolver).evidence_refs,
            ["evidence:a", "evidence:c"]
        );
    }

    #[test]
    fn diagnostics_cover_missing_source_field_value_and_revision() {
        let mut state = factorization();
        assert!(state
            .apply(None, &[(F::Remaining, V::Int(11))], &[])
            .is_none());
        assert!(state
            .apply(RU, &[(F::Remaining, V::Int(-1))], &[])
            .is_none());
        assert!(state
            .apply(RU, &[(F::GoalStatus, V::String("DONE".into()))], &[])
            .is_none());
        let unknown = serde_json::json!({"not_a_field": 1});
        assert!(state
            .apply_json(RU, unknown.as_object().unwrap(), &[])
            .is_none());
        let bad_goal = serde_json::json!({"goal_status": "DONE"});
        assert!(state
            .apply_json(RU, bad_goal.as_object().unwrap(), &[])
            .is_none());
        assert_eq!(state.revision(), 0, "rejected updates must not mutate");
        state
            .apply(RU, &[(F::CurrentCandidate, V::Int(7))], &[])
            .unwrap();
        assert_eq!(
            state.initialize(&[(F::Remaining, V::Int(5))]),
            Err("RUS-004")
        );
        assert_eq!(
            state.diagnostics(),
            ["RUS-001", "RUS-003", "RUS-002", "RUS-004"]
        );
        let reached = serde_json::json!({"goal_status": "REACHED"});
        assert!(state
            .apply_json(RU, reached.as_object().unwrap(), &[])
            .is_some());
        assert_eq!(state.goal_status(), GoalStatus::Reached);
    }

    #[test]
    fn replay_reconstructs_final_state_and_rejects_broken_revisions() {
        let mut state = factorization();
        let transitions: Vec<_> = [
            vec![(F::CurrentCandidate, V::Int(7))],
            vec![(F::Remaining, V::Int(11)), (F::SearchBound, V::Int(3))],
            vec![(F::GoalStatus, V::Goal(GoalStatus::Reached))],
        ]
        .iter()
        .map(|updates| state.apply(RU, updates, &[]).unwrap())
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
            state.apply(RU, &[(F::Remaining, V::Int(remaining))], &[]);
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
                Ok(Some(StateEffect::Update1(updates))) => Ok(Some(updates.to_vec())),
                Ok(Some(StateEffect::Update2(updates))) => Ok(Some(updates.to_vec())),
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

    fn edge_values() -> Vec<V> {
        vec![
            V::None,
            V::Int(0),
            V::Int(-7),
            V::Int(i64::MAX),
            V::Int(i64::MIN),
            V::Bool(true),
            V::Bool(false),
            V::String("quote \" slash \\ line\n tab\t ctl\u{1} \u{7f} 雪 é".into()),
            V::String(String::new()),
            V::Json(Rc::new(serde_json::json!({
                "type_name": "Candidate",
                "fields": {"value": 7, "label": "a\"b", "ratio": 1.5, "tiny": 1.0e-12,
                           "big": 1.0e100, "list": [null, true, "é", -0.0, 2.5e-9]}
            }))),
            V::Json(Rc::new(
                serde_json::json!([1.5, -12.25, {"nested": {"k": []}}]),
            )),
            V::Json(Rc::new(serde_json::json!(u64::MAX))),
            V::Json(Rc::new(serde_json::json!(1.0e-7))),
        ]
    }

    #[test]
    fn streamed_canonical_bytes_equal_the_serde_artifact_bytes() {
        let mut state = factorization();
        let mut transitions = Vec::new();
        for (index, candidate) in edge_values().into_iter().enumerate() {
            let refs: Vec<_> = (0..index % 4).map(|n| EvidenceRef(3 - n as u32)).collect();
            let remaining = 70 - index as i64;
            let updates = [
                (F::CurrentCandidate, candidate),
                (F::Remaining, V::Int(remaining)),
                (F::SearchBound, V::Int(remaining.isqrt())),
                (F::ActiveConstraintCount, V::Int(index as i64)),
            ];
            let source = Some(RuRef((index % 4) as u32));
            transitions.push(state.apply(source, &updates, &refs).unwrap());
        }
        let goal = [(F::GoalStatus, V::Goal(GoalStatus::Reached))];
        transitions.push(state.apply(RU, &goal, &[]).unwrap());
        for transition in &transitions {
            let mut streamed = Vec::new();
            transition.write_canonical(&mut streamed, &TestResolver);
            let reference = serde_json::to_vec(&transition.to_artifact(&TestResolver)).unwrap();
            assert_eq!(
                String::from_utf8(streamed).unwrap(),
                String::from_utf8(reference).unwrap()
            );
        }
        let artifacts: Vec<_> = transitions
            .iter()
            .map(|transition| transition.to_artifact(&TestResolver))
            .collect();
        let reference = |bytes: Vec<u8>| format!("sha256:{:x}", Sha256::digest(bytes));
        assert_eq!(
            transition_hash(&transitions, &TestResolver),
            reference(serde_json::to_vec(&artifacts).unwrap())
        );
        assert_eq!(
            transition_hash(&[], &TestResolver),
            reference(serde_json::to_vec::<[StateTransition]>(&[]).unwrap())
        );
        assert_eq!(
            transition_hash(&transitions[..1], &TestResolver),
            reference(serde_json::to_vec(&artifacts[..1]).unwrap())
        );
    }

    #[test]
    fn streamed_state_hash_equals_the_serde_canonical_hash() {
        #[derive(Serialize)]
        struct Canonical {
            revision: u64,
            fields: BTreeMap<&'static str, serde_json::Value>,
        }
        for candidate in edge_values() {
            let mut state = factorization();
            // `None` equals the initial candidate, so that update is a no-op.
            state.apply(RU, &[(F::CurrentCandidate, candidate)], &[]);
            state
                .apply(RU, &[(F::GoalStatus, V::Goal(GoalStatus::Reached))], &[])
                .unwrap();
            let trace = state.trace();
            let canonical = Canonical {
                revision: state.revision(),
                fields: trace.fields.clone(),
            };
            let reference = format!(
                "sha256:{:x}",
                Sha256::digest(serde_json::to_vec(&canonical).unwrap())
            );
            assert_eq!(state.hash(), reference);
            assert_eq!(state.hash(), trace.hash);
        }
        let initial = factorization();
        let canonical = Canonical {
            revision: 0,
            fields: initial.trace().fields,
        };
        assert_eq!(
            initial.initial_hash(),
            format!(
                "sha256:{:x}",
                Sha256::digest(serde_json::to_vec(&canonical).unwrap())
            )
        );
    }

    #[test]
    fn changed_mask_iterates_in_external_name_order() {
        let mask = FieldMask(F::SearchBound.bit() | F::GoalStatus.bit() | F::Remaining.bit());
        let names: Vec<_> = mask.by_name().map(F::name).collect();
        assert_eq!(names, ["goal_status", "remaining", "search_bound"]);
        assert_eq!(mask.count(), 3);
        assert_eq!(
            F::BY_NAME.map(F::index).iter().copied().max(),
            Some(F::COUNT - 1)
        );
    }
}
