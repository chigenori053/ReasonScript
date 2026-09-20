//! RUS / RUO semantic projection (RUS / RUO Runtime Integration v0.1).
//!
//! `RuntimeReasoningState` stays the source of truth on the hot path. This module
//! only *projects* what the runtime already keeps — the Executable RU table, the
//! typed state transitions, Evidence, ReasonRelations, and the causal relations —
//! into immutable semantic objects when the response is constructed:
//!
//! * a `ReasonUnitState` (RUS) per state revision, and
//! * a `ReasonUnitObject` (RUO) per Executable RU, binding the RU, its RUS
//!   before/after, Evidence, and relation references (it never copies them).
//!
//! Nothing here runs while the program executes.

use crate::causal::CausalRelation;
use crate::reason_structure::{terminal_status, ExecutableReasonUnit};
use crate::reasoning_state::{
    apply_after, state_hash, FieldsView, RefResolver, RuRef, RuntimeReasoningState,
    RuntimeStateTransition,
};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::io::Write;
use std::time::Instant;

pub const RUS_SCHEMA: &str = "reason-unit-state/0.1";
pub const RUO_SCHEMA: &str = "reason-unit-object/0.1";

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum ReasonObjectsMode {
    #[default]
    Off,
    Rus,
    RusRuo,
}

impl ReasonObjectsMode {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "off" => Some(Self::Off),
            "rus" => Some(Self::Rus),
            "rus_ruo" => Some(Self::RusRuo),
            _ => None,
        }
    }

    pub fn enabled(self) -> bool {
        self != Self::Off
    }

    fn name(self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Rus => "rus",
            Self::RusRuo => "rus_ruo",
        }
    }
}

/// Immutable semantic projection of one `RuntimeReasoningState` revision.
#[derive(Clone, Debug, Serialize)]
pub struct ReasonUnitState {
    pub id: String,
    pub revision: u64,
    pub parent_revision: Option<u64>,
    pub fields: FieldsView,
    pub source_ru_ref: Option<String>,
    pub evidence_refs: Vec<String>,
    pub transition_ref: Option<String>,
    pub semantic_state_hash: String,
}

/// State-level relation: `READS_STATE` (RUS → RU), `UPDATES` (RU → RUS after),
/// `DERIVES_STATE` (parent RUS → RUS).
#[derive(Clone, Debug, Serialize)]
pub struct RusRelation {
    pub id: String,
    pub kind: &'static str,
    pub source_ref: String,
    pub target_ref: String,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct RusMetrics {
    pub rus_projection_count: u64,
    pub rus_relation_count: u64,
    pub rus_materialization_ns: u64,
    pub rus_hash_ns: u64,
    pub dangling_reference_count: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct RusTrace {
    pub schema: &'static str,
    pub mode: &'static str,
    pub states: Vec<ReasonUnitState>,
    pub relations: Vec<RusRelation>,
    pub hashes: BTreeMap<&'static str, String>,
    pub metrics: RusMetrics,
    pub diagnostics: Vec<&'static str>,
}

/// One Executable RU bound to its RUS before/after, Evidence, and relations.
#[derive(Clone, Debug, Serialize)]
pub struct ReasonUnitObject {
    pub id: String,
    pub ru_ref: String,
    pub rus_before_ref: String,
    pub rus_after_ref: String,
    pub evidence_refs: Vec<String>,
    pub relation_refs: Vec<String>,
    pub causal_relation_refs: Vec<String>,
    pub lifecycle: Vec<&'static str>,
    pub status: &'static str,
    pub semantic_signature: String,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct RuoMetrics {
    pub ruo_count: u64,
    pub ruo_materialization_ns: u64,
    pub ruo_hash_ns: u64,
    pub dangling_reference_count: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct RuoTrace {
    pub schema: &'static str,
    pub objects: Vec<ReasonUnitObject>,
    pub hashes: BTreeMap<&'static str, String>,
    pub metrics: RuoMetrics,
    pub diagnostics: Vec<&'static str>,
}

#[derive(Clone, Debug)]
pub struct ReasonObjectsTrace {
    pub rus: RusTrace,
    pub ruo: Option<RuoTrace>,
}

/// Read-only view of the runtime tables the projection is built from.
pub(crate) struct ObjectSources<'a> {
    pub units: &'a [ExecutableReasonUnit],
    pub evidence: &'a [serde_json::Value],
    pub relations: &'a [serde_json::Value],
    pub state: &'a RuntimeReasoningState,
    pub transitions: &'a [RuntimeStateTransition],
}

fn rus_id(revision: u64) -> String {
    format!("rus:runtime:{revision:08}")
}

fn transition_id(revision: u64) -> String {
    format!("state-transition:{revision:08}")
}

/// Canonical record encoding for the RUS / RUO hashes: a compact JSON array of
/// fixed-position records, streamed into SHA-256 (no artifact tree is
/// serialized). A state's fields are committed by its `semantic_state_hash`.
fn push_str(buf: &mut Vec<u8>, value: &str) {
    if value
        .bytes()
        .all(|b| (0x20..0x7f).contains(&b) && b != b'"' && b != b'\\')
    {
        buf.push(b'"');
        buf.extend_from_slice(value.as_bytes());
        buf.push(b'"');
    } else {
        serde_json::to_writer(&mut *buf, value).expect("writing to a Vec cannot fail");
    }
}

fn push_opt(buf: &mut Vec<u8>, value: Option<&str>) {
    match value {
        Some(value) => push_str(buf, value),
        None => buf.extend_from_slice(b"null"),
    }
}

fn push_list<S: AsRef<str>>(buf: &mut Vec<u8>, values: &[S]) {
    buf.push(b'[');
    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            buf.push(b',');
        }
        push_str(buf, value.as_ref());
    }
    buf.push(b']');
}

fn record_hash<T>(items: &[T], write: impl Fn(&mut Vec<u8>, &T)) -> String {
    let mut hasher = Sha256::new();
    let mut buf = Vec::with_capacity(512);
    hasher.update(b"[");
    for (index, item) in items.iter().enumerate() {
        buf.clear();
        if index > 0 {
            buf.push(b',');
        }
        write(&mut buf, item);
        hasher.update(&buf);
    }
    hasher.update(b"]");
    format!("sha256:{:x}", hasher.finalize())
}

/// `[id, parent_revision, source_ru_ref, transition_ref, evidence_refs, semantic_state_hash]`
pub fn rus_sequence_hash(states: &[ReasonUnitState]) -> String {
    record_hash(states, |buf, state| {
        buf.push(b'[');
        push_str(buf, &state.id);
        buf.push(b',');
        match state.parent_revision {
            Some(parent) => {
                let _ = write!(buf, "{parent}");
            }
            None => buf.extend_from_slice(b"null"),
        }
        buf.push(b',');
        push_opt(buf, state.source_ru_ref.as_deref());
        buf.push(b',');
        push_opt(buf, state.transition_ref.as_deref());
        buf.push(b',');
        push_list(buf, &state.evidence_refs);
        buf.push(b',');
        push_str(buf, &state.semantic_state_hash);
        buf.push(b']');
    })
}

/// `[id, kind, source_ref, target_ref]`
pub fn rus_relation_hash(relations: &[RusRelation]) -> String {
    record_hash(relations, |buf, relation| {
        buf.push(b'[');
        for (index, part) in [
            &relation.id,
            relation.kind,
            &relation.source_ref,
            &relation.target_ref,
        ]
        .into_iter()
        .enumerate()
        {
            if index > 0 {
                buf.push(b',');
            }
            push_str(buf, part);
        }
        buf.push(b']');
    })
}

/// `[id, ru_ref, rus_before_ref, rus_after_ref, evidence_refs, relation_refs,
/// causal_relation_refs, lifecycle, status, semantic_signature]`
pub fn ruo_graph_hash(objects: &[ReasonUnitObject]) -> String {
    record_hash(objects, |buf, object| {
        buf.push(b'[');
        for part in [
            &object.id,
            &object.ru_ref,
            &object.rus_before_ref,
            &object.rus_after_ref,
        ] {
            push_str(buf, part);
            buf.push(b',');
        }
        for list in [
            &object.evidence_refs,
            &object.relation_refs,
            &object.causal_relation_refs,
        ] {
            push_list(buf, list);
            buf.push(b',');
        }
        push_list(buf, &object.lifecycle);
        buf.push(b',');
        push_str(buf, object.status);
        buf.push(b',');
        push_str(buf, &object.semantic_signature);
        buf.push(b']');
    })
}

fn elapsed(started: Instant) -> u64 {
    started.elapsed().as_nanos() as u64
}

fn ids(values: &[serde_json::Value]) -> impl Iterator<Item = &str> {
    values.iter().filter_map(|value| value["id"].as_str())
}

pub(crate) fn project(
    sources: &ObjectSources,
    resolver: &dyn RefResolver,
    mode: ReasonObjectsMode,
    causal: &[CausalRelation],
) -> ReasonObjectsTrace {
    let started = Instant::now();
    let units = sources.units;
    let transitions = sources.transitions;
    let state = sources.state;
    let mut rus_diagnostics = Vec::new();

    // RUS revisions: replay the typed transitions from the initial state.
    let mut fields = state.initial_fields().clone();
    let mut states = Vec::with_capacity(transitions.len() + 1);
    states.push(ReasonUnitState {
        id: rus_id(0),
        revision: 0,
        parent_revision: None,
        fields: FieldsView(fields.clone()),
        source_ru_ref: state
            .initial_source_ru()
            .map(|ru| resolver.ru_id(ru).to_owned()),
        evidence_refs: Vec::new(),
        transition_ref: None,
        semantic_state_hash: state_hash(0, &fields),
    });
    let mut updated_at: Vec<Option<u64>> = vec![None; units.len()];
    for transition in transitions {
        apply_after(&mut fields, transition);
        let revision = transition.revision_after();
        let RuRef(index) = transition.source_ru;
        if let Some(slot) = updated_at.get_mut(index as usize) {
            *slot = Some(revision);
        }
        let mut evidence_refs: Vec<String> = transition
            .evidence
            .as_slice()
            .iter()
            .map(|evidence| resolver.evidence_id(*evidence).to_owned())
            .collect();
        evidence_refs.sort();
        states.push(ReasonUnitState {
            id: rus_id(revision),
            revision,
            parent_revision: Some(revision - 1),
            fields: FieldsView(fields.clone()),
            source_ru_ref: Some(resolver.ru_id(transition.source_ru).to_owned()),
            evidence_refs,
            transition_ref: Some(transition_id(revision)),
            semantic_state_hash: state_hash(revision, &fields),
        });
    }
    if states.len() as u64 != state.revision() + 1 {
        rus_diagnostics.push("RUS-PROJ-001");
    } else if states.last().map(|last| &last.semantic_state_hash) != Some(&state.hash()) {
        rus_diagnostics.push("RUS-PROJ-003");
    }
    if states.iter().enumerate().any(|(index, s)| {
        s.revision != index as u64 || s.parent_revision != index.checked_sub(1).map(|p| p as u64)
    }) {
        rus_diagnostics.push("RUS-PROJ-002");
    }

    // Each RU's RUS before (state when it began) and after (its own transition, if any).
    let bindings: Vec<(u64, u64)> = units
        .iter()
        .zip(&updated_at)
        .map(|(unit, updated)| {
            let before = u64::from(unit.state_before);
            (before, updated.unwrap_or(before))
        })
        .collect();

    // State-level relations, in RU execution order.
    let mut relations: Vec<RusRelation> = Vec::with_capacity(units.len() * 2);
    let mut relation_indexes: Vec<[u32; 3]> = vec![[u32::MAX; 3]; units.len()];
    fn push_relation(
        relations: &mut Vec<RusRelation>,
        kind: &'static str,
        source: String,
        target: String,
    ) -> u32 {
        relations.push(RusRelation {
            id: format!("relation:rus:{:08}", relations.len() + 1),
            kind,
            source_ref: source,
            target_ref: target,
        });
        relations.len() as u32 - 1
    }
    for (index, (unit, (before, after))) in units.iter().zip(&bindings).enumerate() {
        relation_indexes[index][0] = push_relation(
            &mut relations,
            "READS_STATE",
            rus_id(*before),
            unit.id.clone(),
        );
        if updated_at[index].is_some() {
            relation_indexes[index][1] =
                push_relation(&mut relations, "UPDATES", unit.id.clone(), rus_id(*after));
            relation_indexes[index][2] = push_relation(
                &mut relations,
                "DERIVES_STATE",
                rus_id(*after - 1),
                rus_id(*after),
            );
        }
    }
    let rus_materialization_ns = elapsed(started);

    let started = Instant::now();
    let mut rus_hashes = BTreeMap::new();
    rus_hashes.insert("rus_sequence_hash", rus_sequence_hash(&states));
    rus_hashes.insert("rus_relation_hash", rus_relation_hash(&relations));
    let rus_hash_ns = elapsed(started);

    let ruo = (mode == ReasonObjectsMode::RusRuo).then(|| {
        project_objects(
            sources,
            causal,
            &states,
            &relations,
            &bindings,
            &relation_indexes,
            &updated_at,
        )
    });

    // Referential integrity of the RUS side: RU, Evidence, and transition references.
    let ru_ids: HashSet<&str> = units.iter().map(|unit| unit.id.as_str()).collect();
    let evidence_ids: HashSet<&str> = ids(sources.evidence).collect();
    let rus_ids: HashSet<&str> = states.iter().map(|s| s.id.as_str()).collect();
    let known = |id: &str| ru_ids.contains(id) || rus_ids.contains(id);
    let rus_dangling = states
        .iter()
        .map(|s| {
            usize::from(
                s.source_ru_ref
                    .as_deref()
                    .is_some_and(|ru| !ru_ids.contains(ru)),
            ) + s
                .evidence_refs
                .iter()
                .filter(|e| !evidence_ids.contains(e.as_str()))
                .count()
        })
        .sum::<usize>()
        + relations
            .iter()
            .map(|r| usize::from(!known(&r.source_ref)) + usize::from(!known(&r.target_ref)))
            .sum::<usize>();

    ReasonObjectsTrace {
        rus: RusTrace {
            schema: RUS_SCHEMA,
            mode: mode.name(),
            metrics: RusMetrics {
                rus_projection_count: states.len() as u64,
                rus_relation_count: relations.len() as u64,
                rus_materialization_ns,
                rus_hash_ns,
                dangling_reference_count: rus_dangling as u64,
            },
            states,
            relations,
            hashes: rus_hashes,
            diagnostics: rus_diagnostics,
        },
        ruo,
    }
}

#[allow(clippy::too_many_arguments)]
fn project_objects(
    sources: &ObjectSources,
    causal: &[CausalRelation],
    states: &[ReasonUnitState],
    rus_relations: &[RusRelation],
    bindings: &[(u64, u64)],
    relation_indexes: &[[u32; 3]],
    updated_at: &[Option<u64>],
) -> RuoTrace {
    let started = Instant::now();
    let units = sources.units;
    let mut diagnostics: Vec<&'static str> = Vec::new();
    let mut note = |code: &'static str| {
        if !diagnostics.contains(&code) {
            diagnostics.push(code);
        }
    };

    // ReasonRelations that touch an RU (as source or target), in table order.
    let mut reason_by_end: HashMap<&str, Vec<&str>> = HashMap::with_capacity(units.len());
    for relation in sources.relations {
        let Some(id) = relation["id"].as_str() else {
            continue;
        };
        for end in ["source_ref", "target_ref"] {
            if let Some(end) = relation[end].as_str() {
                let refs = reason_by_end.entry(end).or_default();
                if refs.last() != Some(&id) {
                    refs.push(id);
                }
            }
        }
    }
    // Causal relations by endpoint (RU or state-transition ID).
    let mut causal_by_end: HashMap<&str, Vec<&str>> = HashMap::with_capacity(units.len());
    for relation in causal {
        for end in [relation.source_ref.as_str(), relation.target_ref.as_str()] {
            let refs = causal_by_end.entry(end).or_default();
            if refs.last() != Some(&relation.id.as_str()) {
                refs.push(&relation.id);
            }
        }
    }

    let mut objects = Vec::with_capacity(units.len());
    for (index, unit) in units.iter().enumerate() {
        let (before, after) = bindings[index];
        let mut evidence_refs = unit.evidence_refs.clone();
        evidence_refs.sort();
        let mut relation_refs: Vec<String> = reason_by_end
            .get(unit.id.as_str())
            .map(|refs| refs.iter().map(|id| (*id).to_owned()).collect())
            .unwrap_or_default();
        relation_refs.extend(
            relation_indexes[index]
                .iter()
                .filter(|slot| **slot != u32::MAX)
                .map(|slot| rus_relations[*slot as usize].id.clone()),
        );
        let mut causal_relation_refs: Vec<String> = causal_by_end
            .get(unit.id.as_str())
            .into_iter()
            .flatten()
            .map(|id| (*id).to_owned())
            .collect();
        if let Some(revision) = updated_at[index] {
            causal_relation_refs.extend(
                causal_by_end
                    .get(transition_id(revision).as_str())
                    .into_iter()
                    .flatten()
                    .map(|id| (*id).to_owned()),
            );
        }
        causal_relation_refs.sort();
        causal_relation_refs.dedup();
        objects.push(ReasonUnitObject {
            id: format!("ruo:{}", unit.id),
            ru_ref: unit.id.clone(),
            rus_before_ref: rus_id(before),
            rus_after_ref: rus_id(after),
            evidence_refs,
            relation_refs,
            causal_relation_refs,
            lifecycle: unit.lifecycle.clone(),
            status: unit.terminal_status.map_or("ACTIVE", terminal_status),
            semantic_signature: unit.semantic_signature.clone(),
        });
    }
    let ruo_materialization_ns = elapsed(started);

    // Referential integrity: every reference must resolve.
    let ru_ids: HashSet<&str> = units.iter().map(|unit| unit.id.as_str()).collect();
    let rus_ids: HashSet<&str> = states.iter().map(|s| s.id.as_str()).collect();
    let evidence_ids: HashSet<&str> = ids(sources.evidence).collect();
    let relation_ids: HashSet<&str> = ids(sources.relations)
        .chain(rus_relations.iter().map(|r| r.id.as_str()))
        .collect();
    let causal_ids: HashSet<&str> = causal.iter().map(|r| r.id.as_str()).collect();
    let mut seen: HashSet<&str> = HashSet::with_capacity(objects.len());
    let mut dangling = 0_u64;
    for object in &objects {
        if !seen.insert(object.id.as_str()) {
            note("RUO-006");
        }
        if !ru_ids.contains(object.ru_ref.as_str()) {
            dangling += 1;
            note("RUO-001");
        }
        for rus in [&object.rus_before_ref, &object.rus_after_ref] {
            if !rus_ids.contains(rus.as_str()) {
                dangling += 1;
                note("RUO-003");
            }
        }
        for evidence in &object.evidence_refs {
            if !evidence_ids.contains(evidence.as_str()) {
                dangling += 1;
                note("RUO-004");
            }
        }
        for relation in &object.relation_refs {
            if !relation_ids.contains(relation.as_str()) {
                dangling += 1;
                note("RUO-005");
            }
        }
        for relation in &object.causal_relation_refs {
            if !causal_ids.contains(relation.as_str()) {
                dangling += 1;
                note("RUO-005");
            }
        }
    }

    let started = Instant::now();
    let mut hashes = BTreeMap::new();
    hashes.insert("ruo_graph_hash", ruo_graph_hash(&objects));
    let ruo_hash_ns = elapsed(started);
    RuoTrace {
        schema: RUO_SCHEMA,
        metrics: RuoMetrics {
            ruo_count: objects.len() as u64,
            ruo_materialization_ns,
            ruo_hash_ns,
            dangling_reference_count: dangling,
        },
        objects,
        hashes,
        diagnostics,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::reason_structure::{ExecutableMode, ReasonStructure};
    use crate::reasoning_state::ReasoningStateMode;
    use crate::state_causality::StateCausalityMode;

    /// The N=77 factorization event sequence, run through the real RU machinery.
    fn factorization(
        causality: StateCausalityMode,
        objects: ReasonObjectsMode,
    ) -> (ReasonStructure, Vec<CausalRelation>) {
        let mut structure = ReasonStructure::default();
        structure.set_executable_mode(ExecutableMode::Full);
        structure.set_reasoning_state_mode(ReasoningStateMode::Lightweight);
        structure.set_state_causality_mode(causality);
        structure.set_reason_objects_mode(objects);
        for (event, subject) in [
            ("REASON_STATE_CREATED", 77),
            ("HYPOTHESIS_CREATED", 5),
            ("HYPOTHESIS_REJECTED", 5),
            ("HYPOTHESIS_CREATED", 7),
            ("HYPOTHESIS_VERIFIED", 7),
            ("GOAL_UPDATED", 77),
            ("TERMINATION_INFERRED", 77),
        ] {
            structure
                .record_legacy_executable(
                    event,
                    serde_json::json!(subject),
                    serde_json::json!(true),
                )
                .unwrap();
        }
        let mut relations = structure.state_causality_trace().relations;
        for (index, relation) in relations.iter_mut().enumerate() {
            relation.id = format!("causal-relation:{:08}", index + 1);
        }
        (structure, relations)
    }

    fn full() -> ReasonObjectsTrace {
        let (structure, causal) =
            factorization(StateCausalityMode::Full, ReasonObjectsMode::RusRuo);
        structure.reason_objects_trace(&causal).unwrap()
    }

    #[test]
    fn rus_revisions_are_immutable_projections_of_the_runtime_state() {
        let (structure, causal) =
            factorization(StateCausalityMode::Full, ReasonObjectsMode::RusRuo);
        let trace = structure.reason_objects_trace(&causal).unwrap();
        let states = &trace.rus.states;
        let f = |index: usize, name: &str| {
            serde_json::to_value(&states[index].fields).unwrap()[name].clone()
        };
        assert_eq!(
            states.iter().map(|s| s.revision).collect::<Vec<_>>(),
            [0, 1, 2, 3, 4]
        );
        assert_eq!(states[0].id, "rus:runtime:00000000");
        assert_eq!(
            (states[0].parent_revision, states[3].parent_revision),
            (None, Some(2))
        );
        assert_eq!(f(0, "remaining"), 77);
        assert_eq!(f(0, "search_bound"), 8);
        assert_eq!(f(0, "goal_status"), "ACTIVE");
        assert_eq!(
            states[0].source_ru_ref.as_deref(),
            Some("ru:hypothesis:00000001")
        );
        assert_eq!(f(2, "current_candidate"), 7);
        assert_eq!(f(3, "remaining"), 11);
        assert_eq!(f(3, "search_bound"), 3);
        assert_eq!(f(4, "goal_status"), "REACHED");
        assert_eq!(
            states[3].transition_ref.as_deref(),
            Some("state-transition:00000003")
        );
        // the final RUS is the runtime state, by hash
        let runtime = structure.reasoning_state_trace();
        assert_eq!(states[4].semantic_state_hash, runtime.hash);
        assert_eq!(states[0].semantic_state_hash, runtime.initial_hash);
        assert!(trace.rus.diagnostics.is_empty());
        assert_eq!(trace.rus.metrics.dangling_reference_count, 0);
    }

    #[test]
    fn ruo_binds_each_ru_to_its_state_before_and_after() {
        let trace = full();
        let objects = &trace.ruo.as_ref().unwrap().objects;
        assert_eq!(objects.len(), 7);
        let by_ru = |ru: &str| objects.iter().find(|o| o.ru_ref == ru).unwrap();
        let rejected = objects.iter().find(|o| o.status == "REJECTED").unwrap();
        assert_eq!(rejected.rus_before_ref, rejected.rus_after_ref);
        assert!(rejected.semantic_signature.contains("HYPOTHESIS_REJECTED"));
        let verified = objects
            .iter()
            .find(|o| o.status == "VERIFIED" && o.ru_ref.contains("verification"))
            .unwrap();
        assert_eq!(
            (
                verified.rus_before_ref.as_str(),
                verified.rus_after_ref.as_str()
            ),
            ("rus:runtime:00000002", "rus:runtime:00000003")
        );
        assert_eq!(verified.id, format!("ruo:{}", verified.ru_ref));
        assert_eq!(verified.evidence_refs.len(), 1);
        let goal = by_ru("ru:goal-evaluation:00000006");
        assert_eq!(
            (goal.rus_before_ref.as_str(), goal.rus_after_ref.as_str()),
            ("rus:runtime:00000003", "rus:runtime:00000004")
        );
        let termination = by_ru("ru:termination-check:00000007");
        assert_eq!(termination.rus_before_ref, termination.rus_after_ref);
        assert_eq!(termination.status, "VERIFIED");
        assert_eq!(
            verified.lifecycle,
            ["CREATED", "ACTIVE", "VERIFIED", "COMPLETED"]
        );
    }

    #[test]
    fn causal_and_relation_refs_resolve_and_include_the_state_change() {
        let (structure, causal) =
            factorization(StateCausalityMode::Full, ReasonObjectsMode::RusRuo);
        let trace = structure.reason_objects_trace(&causal).unwrap();
        let ruo = trace.ruo.unwrap();
        assert!(ruo.diagnostics.is_empty());
        assert_eq!(ruo.metrics.dangling_reference_count, 0);
        let verified = ruo
            .objects
            .iter()
            .find(|o| o.ru_ref.contains("verification") && o.status == "VERIFIED")
            .unwrap();
        let kinds: Vec<&str> = verified
            .causal_relation_refs
            .iter()
            .map(|id| causal.iter().find(|r| &r.id == id).unwrap().relation_kind)
            .collect();
        assert!(kinds.contains(&"CAUSES_STATE_CHANGE"), "{kinds:?}");
        assert!(kinds.contains(&"ENABLES"), "{kinds:?}");
        assert!(verified
            .relation_refs
            .iter()
            .any(|r| r.starts_with("relation:ru:")));
        assert!(verified
            .relation_refs
            .iter()
            .any(|r| r.starts_with("relation:rus:")));
        assert_eq!(
            trace
                .rus
                .relations
                .iter()
                .filter(|r| r.kind == "UPDATES")
                .count(),
            4
        );
        assert_eq!(
            trace
                .rus
                .relations
                .iter()
                .filter(|r| r.kind == "DERIVES_STATE")
                .count(),
            4
        );
        assert_eq!(
            trace
                .rus
                .relations
                .iter()
                .filter(|r| r.kind == "READS_STATE")
                .count(),
            7
        );
    }

    #[test]
    fn projection_is_deterministic_and_mode_gated() {
        let (first, second) = (full(), full());
        assert_eq!(first.rus.hashes, second.rus.hashes);
        assert_eq!(
            first.ruo.as_ref().unwrap().hashes,
            second.ruo.as_ref().unwrap().hashes
        );
        let (structure, causal) = factorization(StateCausalityMode::Full, ReasonObjectsMode::Rus);
        let rus_only = structure.reason_objects_trace(&causal).unwrap();
        assert!(rus_only.ruo.is_none());
        assert_eq!(rus_only.rus.hashes, first.rus.hashes);
        let (structure, causal) = factorization(StateCausalityMode::Full, ReasonObjectsMode::Off);
        assert!(structure.reason_objects_trace(&causal).is_none());
    }

    #[test]
    fn rus_projection_keeps_transitions_without_reporting_state_causality() {
        let (structure, causal) = factorization(StateCausalityMode::Off, ReasonObjectsMode::Rus);
        let trace = structure.reason_objects_trace(&causal).unwrap();
        assert_eq!(trace.rus.states.len(), 5);
        assert_eq!(
            trace.rus.states.last().unwrap().semantic_state_hash,
            structure.reasoning_state_trace().hash
        );
        let reported = structure.state_causality_trace();
        assert!(reported.transitions.is_empty() && reported.relations.is_empty());
        assert_eq!(reported.metrics.state_transition_count, 0);
    }

    #[test]
    fn hash_strings_are_written_exactly_like_serde_json() {
        for value in [
            "",
            "ru:verification:00000007",
            "quote \" slash \\ line\n tab\t ctl\u{1} del\u{7f}",
            "雪 é 😀",
            "VERIFICATION|HYPOTHESIS_VERIFIED|7|null",
        ] {
            let mut streamed = Vec::new();
            push_str(&mut streamed, value);
            assert_eq!(streamed, serde_json::to_vec(value).unwrap(), "{value:?}");
        }
    }

    #[test]
    fn missing_transitions_are_diagnosed() {
        // Projection enabled only after the run: nothing was retained.
        let (mut structure, causal) =
            factorization(StateCausalityMode::Off, ReasonObjectsMode::Off);
        structure.set_reason_objects_mode(ReasonObjectsMode::Rus);
        let trace = structure.reason_objects_trace(&causal).unwrap();
        assert!(trace.rus.diagnostics.contains(&"RUS-PROJ-001"));
    }
}
