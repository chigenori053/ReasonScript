//! Native ReasonUnit Object runtime core (RUO-N1).
//!
//! The core deliberately uses ordered collections and safe Rust only. Stable
//! semantic identity never depends on an address, slot, worker, or tensor index.

use serde::{Deserialize, Serialize};
use serde_json::value::RawValue;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::sync::{Arc, RwLock};

pub const PROFILE: &str = "reasonscript-reasonunit-native-runtime/1.0";
pub const NATIVE_REASON_GRAPH_PROFILE: &str = "reasonscript-reason-object-graph-native/0.1";
pub const NATIVE_REASON_GRAPH_QUERY_PROFILE: &str = "reasonscript-reason-object-graph-native-query/0.1";

#[derive(Deserialize)]
struct RawEnvelope {
    body: Box<RawValue>,
    body_sha256: String,
    record_type: String,
}

#[derive(Deserialize)]
struct RgoEnvelope {
    body: Box<RawValue>,
    body_sha256: String,
    ordinal: u64,
    record_type: String,
    record_version: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Ord, PartialOrd, Serialize, Deserialize)]
pub struct StableId(String);

impl StableId {
    pub fn new(value: impl Into<String>) -> Result<Self, NativeError> {
        let value = value.into();
        if value.is_empty() || !value.contains(':') || value.bytes().any(|b| b <= 0x20) {
            return Err(NativeError::new(
                "RUO-N1-003",
                FailureClass::Semantic,
                "invalid namespaced stable ID",
            ));
        }
        Ok(Self(value))
    }
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LoadState {
    MetadataOnly,
    NotLoaded,
    PartiallyLoaded,
    Materialized,
    Evicted,
    Unavailable,
    Invalid,
    Deleted,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EntityKind {
    Object,
    AtomicUnit,
    CompositeUnit,
    Payload,
    State,
    Relation,
    Evidence,
    Constraint,
    Dependency,
    Lifecycle,
    Revision,
    Extension,
    TensorView,
    ExecutionProjection,
}

macro_rules! native_record {
    ($name:ident) => {
        #[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
        pub struct $name {
            pub id: StableId,
            pub owner_id: StableId,
            pub revision: u64,
            pub value: Value,
        }
    };
}
native_record!(NativeAtomicReasonUnit);
native_record!(NativeCompositeReasonUnit);
native_record!(NativePayload);
native_record!(NativeStateRecord);
native_record!(NativeRelation);
native_record!(NativeEvidenceRecord);
native_record!(NativeConstraint);
native_record!(NativeDependency);
native_record!(NativeLifecycle);
native_record!(NativeRevision);
native_record!(NativeExtension);
native_record!(NativeTensorView);
native_record!(NativeExecutionProjection);

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct NativeEntity {
    pub id: StableId,
    pub owner_id: StableId,
    pub kind: EntityKind,
    pub revision: u64,
    pub load_state: LoadState,
    pub execution_eligible: bool,
    pub value: Value,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct NativeReasonUnitObject {
    pub object_id: StableId,
    pub revision_id: StableId,
    pub roots: BTreeSet<StableId>,
    pub entities: BTreeMap<StableId, NativeEntity>,
    pub logical: Value,
    pub logical_digest: String,
    #[serde(skip)]
    pub canonical_bytes: Option<Vec<u8>>,
}

/// Verified, immutable view of an RGO-F1 ReasonGraph.
///
/// This deliberately has no mutation or execution API.  Its sole role is to
/// establish native-runtime parity for canonical graph persistence.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct NativeReasonGraph {
    pub graph_id: StableId,
    pub graph_hash: String,
    pub units: BTreeSet<StableId>,
    pub relation_ids: BTreeSet<StableId>,
    pub logical: Value,
    #[serde(skip)]
    pub canonical_bytes: Option<Vec<u8>>,
}

impl NativeReasonUnitObject {
    pub fn from_logical(logical: Value) -> Result<Self, NativeError> {
        let object_id = StableId::new(string_at(&logical, &["object_identity", "entity_id"])?)?;
        let revision_id = StableId::new(string_at(&logical, &["current_revision"])?)?;
        let mut entities = BTreeMap::new();
        let sections = [
            ("units", "entity_id", EntityKind::AtomicUnit),
            ("payloads", "payload_id", EntityKind::Payload),
            ("states", "state_id", EntityKind::State),
            ("relations", "relation_id", EntityKind::Relation),
            ("constraints", "constraint_id", EntityKind::Constraint),
            ("evidence_registry", "evidence_id", EntityKind::Evidence),
            ("revisions", "revision_id", EntityKind::Revision),
            (
                "projection_descriptors",
                "projection_id",
                EntityKind::ExecutionProjection,
            ),
        ];
        for (section, key, default_kind) in sections {
            for value in logical
                .get(section)
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let id = StableId::new(
                    value
                        .get(key)
                        .and_then(Value::as_str)
                        .ok_or_else(|| NativeError::semantic("entity ID missing"))?,
                )?;
                let owner = value
                    .get("owner_id")
                    .and_then(Value::as_str)
                    .unwrap_or(object_id.as_str());
                let kind = if section == "units"
                    && value.get("unit_kind").and_then(Value::as_str) == Some("composite")
                {
                    EntityKind::CompositeUnit
                } else {
                    default_kind
                };
                let entity = NativeEntity {
                    id: id.clone(),
                    owner_id: StableId::new(owner)?,
                    kind,
                    revision: 1,
                    load_state: LoadState::Materialized,
                    execution_eligible: true,
                    value: value.clone(),
                };
                if entities.insert(id, entity).is_some() {
                    return Err(NativeError::semantic("duplicate stable ID"));
                }
            }
        }
        for ext in logical
            .get("extension_registry")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            let namespace = ext
                .get("namespace")
                .and_then(Value::as_str)
                .ok_or_else(|| NativeError::semantic("extension namespace missing"))?;
            let id = StableId::new(format!("ruo:extension:{namespace}"))?;
            if ext.get("critical") == Some(&Value::Bool(true))
                && ext.get("understood") != Some(&Value::Bool(true))
            {
                return Err(NativeError::new(
                    "RUO-N1-007",
                    FailureClass::Compatibility,
                    "unknown critical extension",
                ));
            }
            entities.insert(
                id.clone(),
                NativeEntity {
                    id,
                    owner_id: object_id.clone(),
                    kind: EntityKind::Extension,
                    revision: 1,
                    load_state: LoadState::Materialized,
                    execution_eligible: false,
                    value: ext.clone(),
                },
            );
        }
        let roots = logical
            .get("root_units")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .map(|v| StableId::new(v.as_str().unwrap_or_default()))
            .collect::<Result<BTreeSet<_>, _>>()?;
        if roots.iter().any(|id| !entities.contains_key(id)) {
            return Err(NativeError::semantic("root is not materialized"));
        }
        let bytes = serde_json::to_vec(&logical)
            .map_err(|_| NativeError::internal("logical serialization failed"))?;
        let logical_digest = sha256(&bytes);
        Ok(Self {
            object_id,
            revision_id,
            roots,
            entities,
            logical,
            logical_digest,
            canonical_bytes: None,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct NativeHandle {
    pub store_id: u64,
    pub generation: u64,
    pub slot: u64,
}

#[derive(Clone, Debug)]
pub struct NativeSnapshot {
    pub object_id: StableId,
    pub revision_id: StableId,
    pub generation: u64,
    pub state_digest: String,
    pub logical_object_digest: String,
    pub object: Arc<NativeReasonUnitObject>,
    handles: Arc<BTreeMap<StableId, u64>>,
}

impl NativeSnapshot {
    pub fn resolve_id(&self, store_id: u64, id: &StableId) -> Result<NativeHandle, NativeError> {
        self.handles
            .get(id)
            .copied()
            .map(|slot| NativeHandle {
                store_id,
                generation: self.generation,
                slot,
            })
            .ok_or_else(|| {
                NativeError::new("RUO-N1-004", FailureClass::Query, "entity is not loaded")
            })
    }
    pub fn resolve_handle(
        &self,
        store_id: u64,
        handle: NativeHandle,
    ) -> Result<&NativeEntity, NativeError> {
        if handle.store_id != store_id || handle.generation != self.generation {
            return Err(NativeError::stale());
        }
        let id = self
            .handles
            .iter()
            .find_map(|(id, slot)| (*slot == handle.slot).then_some(id))
            .ok_or_else(NativeError::stale)?;
        self.object.entities.get(id).ok_or_else(NativeError::stale)
    }
    pub fn query(&self, query: NativeQuery) -> Vec<NativeEntity> {
        self.object
            .entities
            .values()
            .filter(|entity| match &query {
                NativeQuery::All => true,
                NativeQuery::Kind(kind) => &entity.kind == kind,
                NativeQuery::Owner(owner) => &entity.owner_id == owner,
                NativeQuery::LifecycleEligible => {
                    entity.execution_eligible && entity.load_state == LoadState::Materialized
                }
            })
            .cloned()
            .collect()
    }
    pub fn project_execution(
        &self,
        selected: &[StableId],
    ) -> Result<NativeExecutionProjection, NativeError> {
        let ids: Vec<_> = if selected.is_empty() {
            self.query(NativeQuery::LifecycleEligible)
                .into_iter()
                .map(|e| e.id)
                .collect()
        } else {
            selected.to_vec()
        };
        if ids.iter().any(|id| !self.object.entities.contains_key(id)) {
            return Err(NativeError::new(
                "RUO-N1-017",
                FailureClass::Projection,
                "projection contains missing entity",
            ));
        }
        let value = serde_json::json!({"object_id": self.object_id, "revision_id": self.revision_id, "generation": self.generation, "selected_ids": ids, "state_digest": self.state_digest, "logical_digest": self.logical_object_digest});
        Ok(NativeExecutionProjection {
            id: StableId::new(format!("ruo:projection:{}", self.generation))?,
            owner_id: self.object_id.clone(),
            revision: self.generation,
            value,
        })
    }
}

#[derive(Clone, Debug)]
pub enum NativeQuery {
    All,
    Kind(EntityKind),
    Owner(StableId),
    LifecycleEligible,
}

#[derive(Clone, Debug)]
pub enum TransactionOperation {
    Upsert(NativeEntity),
    Delete(StableId),
}

#[derive(Clone, Debug)]
pub struct NativeTransaction {
    pub transaction_id: StableId,
    pub object_id: StableId,
    pub source_generation: u64,
    pub operations: Vec<TransactionOperation>,
}

#[derive(Debug)]
struct StoreState {
    active: BTreeMap<StableId, NativeSnapshot>,
    next_generation: u64,
}

#[derive(Debug)]
pub struct NativeObjectStore {
    store_id: u64,
    inner: RwLock<StoreState>,
    max_entities: usize,
}

impl NativeObjectStore {
    pub fn new(store_id: u64, max_entities: usize) -> Self {
        Self {
            store_id,
            inner: RwLock::new(StoreState {
                active: BTreeMap::new(),
                next_generation: 1,
            }),
            max_entities,
        }
    }
    pub fn insert_object(
        &self,
        object: NativeReasonUnitObject,
    ) -> Result<NativeSnapshot, NativeError> {
        let mut state = self
            .inner
            .write()
            .map_err(|_| NativeError::internal("store lock poisoned"))?;
        if state.active.contains_key(&object.object_id) {
            return Err(NativeError::semantic("duplicate object ID"));
        }
        let snapshot = make_snapshot(&mut state, object, self.max_entities)?;
        state
            .active
            .insert(snapshot.object_id.clone(), snapshot.clone());
        Ok(snapshot)
    }
    pub fn snapshot(&self, id: &StableId) -> Result<NativeSnapshot, NativeError> {
        self.inner
            .read()
            .map_err(|_| NativeError::internal("store lock poisoned"))?
            .active
            .get(id)
            .cloned()
            .ok_or_else(|| NativeError::new("RUO-N1-007", FailureClass::Load, "object not found"))
    }
    pub fn resolve_id(
        &self,
        snapshot: &NativeSnapshot,
        id: &StableId,
    ) -> Result<NativeHandle, NativeError> {
        snapshot.resolve_id(self.store_id, id)
    }
    pub fn resolve_handle<'a>(
        &self,
        snapshot: &'a NativeSnapshot,
        handle: NativeHandle,
    ) -> Result<&'a NativeEntity, NativeError> {
        snapshot.resolve_handle(self.store_id, handle)
    }
    pub fn begin_transaction(
        &self,
        snapshot: &NativeSnapshot,
        transaction_id: StableId,
    ) -> NativeTransaction {
        NativeTransaction {
            transaction_id,
            object_id: snapshot.object_id.clone(),
            source_generation: snapshot.generation,
            operations: vec![],
        }
    }
    pub fn commit_transaction(&self, tx: NativeTransaction) -> Result<NativeSnapshot, NativeError> {
        let mut state = self
            .inner
            .write()
            .map_err(|_| NativeError::internal("store lock poisoned"))?;
        let current = state
            .active
            .get(&tx.object_id)
            .cloned()
            .ok_or_else(|| NativeError::semantic("object not found"))?;
        if current.generation != tx.source_generation {
            return Err(NativeError::new(
                "RUO-N1-011",
                FailureClass::Conflict,
                "stale snapshot transaction",
            ));
        }
        let mut object = (*current.object).clone();
        for op in tx.operations {
            match op {
                TransactionOperation::Upsert(entity) => {
                    if entity.owner_id != object.object_id {
                        return Err(NativeError::semantic("cross-object ownership"));
                    }
                    object.entities.insert(entity.id.clone(), entity);
                }
                TransactionOperation::Delete(id) => {
                    if object.roots.contains(&id) {
                        return Err(NativeError::new(
                            "RUO-N1-013",
                            FailureClass::Lifecycle,
                            "root deletion requires replacement",
                        ));
                    }
                    object.entities.remove(&id);
                }
            }
        }
        object.revision_id = StableId::new(format!("ruo:revision:{}", state.next_generation))?;
        object.logical_digest = sha256(
            serde_json::to_string(&object.entities)
                .map_err(|_| NativeError::internal("state serialization failed"))?
                .as_bytes(),
        );
        object.canonical_bytes = None;
        let next = make_snapshot(&mut state, object, self.max_entities)?;
        state.active.insert(next.object_id.clone(), next.clone());
        Ok(next)
    }
}

fn make_snapshot(
    state: &mut StoreState,
    object: NativeReasonUnitObject,
    max: usize,
) -> Result<NativeSnapshot, NativeError> {
    if object.entities.len() > max {
        return Err(NativeError::new(
            "RUO-N1-023",
            FailureClass::Limit,
            "entity limit exceeded",
        ));
    }
    let generation = state.next_generation;
    state.next_generation = state.next_generation.checked_add(1).ok_or_else(|| {
        NativeError::new("RUO-N1-023", FailureClass::Limit, "generation overflow")
    })?;
    let handles = object
        .entities
        .keys()
        .enumerate()
        .map(|(slot, id)| (id.clone(), slot as u64))
        .collect();
    let state_digest = sha256(
        serde_json::to_string(&object.entities)
            .map_err(|_| NativeError::internal("state serialization failed"))?
            .as_bytes(),
    );
    Ok(NativeSnapshot {
        object_id: object.object_id.clone(),
        revision_id: object.revision_id.clone(),
        generation,
        state_digest,
        logical_object_digest: object.logical_digest.clone(),
        object: Arc::new(object),
        handles: Arc::new(handles),
    })
}

pub fn load_ruo(path: &Path) -> Result<NativeReasonUnitObject, NativeError> {
    let bytes = fs::read(path)
        .map_err(|e| NativeError::new("RUO-N1-007", FailureClass::Load, &e.to_string()))?;
    if !bytes.ends_with(b"\n") || bytes.contains(&b'\r') || bytes.contains(&0) {
        return Err(NativeError::new(
            "RUO-N1-007",
            FailureClass::Integrity,
            "invalid physical RUO stream",
        ));
    }
    let mut logical_object = None;
    let mut sealed_digest = None;
    for line in bytes.split(|b| *b == b'\n').filter(|line| !line.is_empty()) {
        let envelope: RawEnvelope = serde_json::from_slice(line).map_err(|_| {
            NativeError::new(
                "RUO-N1-007",
                FailureClass::Integrity,
                "invalid JSONL record",
            )
        })?;
        let body_bytes = envelope.body.get().as_bytes();
        if envelope.body_sha256 != sha256_hex(body_bytes) {
            return Err(NativeError::new(
                "RUO-N1-007",
                FailureClass::Integrity,
                "record digest mismatch",
            ));
        }
        let body: Value = serde_json::from_str(envelope.body.get()).map_err(|_| {
            NativeError::new("RUO-N1-007", FailureClass::Integrity, "invalid record body")
        })?;
        match envelope.record_type.as_str() {
            "object" => logical_object = Some(body),
            "file_seal" => {
                sealed_digest = body
                    .get("logical_object_digest")
                    .and_then(Value::as_str)
                    .map(str::to_owned)
            }
            _ => {}
        }
    }
    let mut logical = logical_object.ok_or_else(|| {
        NativeError::new(
            "RUO-N1-007",
            FailureClass::Integrity,
            "object record missing",
        )
    })?;
    // Reconstruct section arrays from the authoritative records.
    let mapping = [
        ("unit", "units"),
        ("payload", "payloads"),
        ("state", "states"),
        ("relation", "relations"),
        ("constraint", "constraints"),
        ("evidence", "evidence_registry"),
        ("dependency", "dependency_graph"),
        ("revision", "revisions"),
        ("extension", "extension_registry"),
        ("projection_descriptor", "projection_descriptors"),
        ("external_resource", "external_resources"),
    ];
    for (record_type, field) in mapping {
        let mut values = Vec::new();
        for line in bytes.split(|b| *b == b'\n').filter(|line| !line.is_empty()) {
            let e: Value = serde_json::from_slice(line)
                .map_err(|_| NativeError::internal("record decode failed"))?;
            if e.get("record_type").and_then(Value::as_str) == Some(record_type) {
                values.push(e["body"].clone());
            }
        }
        if !values.is_empty() || logical.get(field).is_some() {
            logical[field] = Value::Array(values);
        }
    }
    let mut object = NativeReasonUnitObject::from_logical(logical)?;
    object.logical_digest = sealed_digest
        .ok_or_else(|| NativeError::new("RUO-N1-007", FailureClass::Integrity, "seal missing"))?;
    object.canonical_bytes = Some(bytes);
    Ok(object)
}

/// Return the native Runtime's read-only graph-relevant view of a RUO-U1 Object.
/// This is deliberately a handoff, not a native ReasonGraph type or executor.
pub fn reason_graph_handoff(object: &NativeReasonUnitObject) -> Result<Value, NativeError> {
    let units = object
        .logical
        .get("units")
        .and_then(Value::as_array)
        .ok_or_else(|| NativeError::semantic("units registry missing"))?
        .iter()
        .map(|unit| {
            let id = unit.get("entity_id").and_then(Value::as_str)
                .ok_or_else(|| NativeError::semantic("unit ID missing"))?;
            Ok(Value::String(id.to_owned()))
        })
        .collect::<Result<Vec<_>, NativeError>>()?;
    let relations = object
        .logical
        .get("relations")
        .and_then(Value::as_array)
        .ok_or_else(|| NativeError::semantic("relations registry missing"))?
        .iter()
        .map(|relation| {
            let relation_id = relation.get("relation_id").and_then(Value::as_str)
                .ok_or_else(|| NativeError::semantic("relation ID missing"))?;
            Ok(serde_json::json!({
                "relation_id": relation_id,
                "source_id": relation.get("source_id"),
                "target_id": relation.get("target_id"),
                "endpoint_resolution": relation.get("endpoint_resolution").unwrap_or(&Value::String("resolved".to_owned())),
            }))
        })
        .collect::<Result<Vec<_>, NativeError>>()?;
    Ok(serde_json::json!({
        "profile": "reasonscript-reason-object-graph-native-handoff/0.1",
        "source_object_id": object.object_id.as_str(),
        "source_revision": object.revision_id.as_str(),
        "logical_object_digest": object.logical_digest,
        "unit_ids": units,
        "relations": relations,
        "read_only": true,
    }))
}

pub fn write_ruo(snapshot: &NativeSnapshot, path: &Path) -> Result<(), NativeError> {
    let bytes = snapshot.object.canonical_bytes.as_ref().ok_or_else(|| {
        NativeError::new(
            "RUO-N1-008",
            FailureClass::Persistence,
            "modified snapshot requires RUO-F1 canonical writer",
        )
    })?;
    fs::write(path, bytes)
        .map_err(|e| NativeError::new("RUO-N1-008", FailureClass::Persistence, &e.to_string()))
}

/// Load a complete RGO-F1 file into an immutable native graph view.
pub fn load_reason_graph(path: &Path) -> Result<NativeReasonGraph, NativeError> {
    let bytes = fs::read(path).map_err(|e| NativeError::new("RGO-N1-001", FailureClass::Load, &e.to_string()))?;
    if bytes.is_empty() || !bytes.ends_with(b"\n") || bytes.iter().any(|byte| *byte == b'\r' || *byte == 0) {
        return Err(NativeError::new("RGO-N1-001", FailureClass::Load, "RGO-F1 must use canonical LF-delimited bytes"));
    }
    let lines: Vec<&[u8]> = bytes[..bytes.len() - 1].split(|byte| *byte == b'\n').collect();
    if lines.len() != 3 || lines.iter().any(|line| line.is_empty()) {
        return Err(NativeError::new("RGO-N1-001", FailureClass::Load, "RGO-F1 must contain exactly three records"));
    }
    let expected_types = ["file_header", "graph", "file_seal"];
    let mut bodies = Vec::new();
    let mut raw_bodies = Vec::new();
    for (ordinal, line) in lines.iter().enumerate() {
        let envelope: RgoEnvelope = serde_json::from_slice(line)
            .map_err(|_| NativeError::new("RGO-N1-001", FailureClass::Load, "invalid RGO-F1 envelope"))?;
        if envelope.ordinal != ordinal as u64 || envelope.record_type != expected_types[ordinal] || envelope.record_version != "1.0" {
            return Err(NativeError::new("RGO-N1-001", FailureClass::Load, "invalid RGO-F1 record order"));
        }
        let raw = envelope.body.get();
        if envelope.body_sha256 != sha256(raw.as_bytes()) {
            return Err(NativeError::new("RGO-N1-002", FailureClass::Integrity, "RGO-F1 record body digest mismatch"));
        }
        let value: Value = serde_json::from_str(raw)
            .map_err(|_| NativeError::new("RGO-N1-001", FailureClass::Load, "invalid RGO-F1 body"))?;
        // The RGO-F1 writer defines canonical bytes.  Do not re-serialize a
        // parsed Value here: JSON implementations may choose a different but
        // numerically equivalent spelling for f64 values.  That would reject
        // valid Python-writer output and would make the digest implementation
        // dependent rather than format dependent.
        raw_bodies.push(raw.to_owned());
        bodies.push(value);
    }
    let header = &bodies[0];
    let logical = bodies[1].clone();
    let seal = &bodies[2];
    if header.get("magic").and_then(Value::as_str) != Some("REASONGRAPH-F1")
        || header.get("format_version").and_then(Value::as_str) != Some("1.0")
        || header.get("canonicalization_profile").and_then(Value::as_str) != Some("reason-object-graph-canonical-jsonl/1")
        || header.get("logical_model").and_then(Value::as_str) != Some("mra-reason-object-graph/0.1")
        || header.get("media_type").and_then(Value::as_str) != Some("application/vnd.reasonscript.reason-graph+jsonl") {
        return Err(NativeError::new("RGO-N1-003", FailureClass::Compatibility, "unsupported RGO-F1 header"));
    }
    let graph_id = StableId::new(required_string(&logical, "graph_id", "RGO-N1-004")?)?;
    if !graph_id.as_str().starts_with("ruo:graph:") {
        return Err(NativeError::new("RGO-N1-004", FailureClass::Semantic, "graph_id must use ruo:graph namespace"));
    }
    if header.get("graph_id").and_then(Value::as_str) != Some(graph_id.as_str())
        || seal.get("graph_id").and_then(Value::as_str) != Some(graph_id.as_str()) {
        return Err(NativeError::new("RGO-N1-002", FailureClass::Integrity, "RGO-F1 graph identity mismatch"));
    }
    let graph_hash = sha256(raw_bodies[1].as_bytes());
    if seal.get("graph_hash").and_then(Value::as_str) != Some(graph_hash.as_str()) {
        return Err(NativeError::new("RGO-N1-002", FailureClass::Integrity, "RGO-F1 graph digest mismatch"));
    }
    let content = [&lines[0][..], b"\n", &lines[1][..], b"\n"].concat();
    if seal.get("content_stream_sha256").and_then(Value::as_str) != Some(sha256(&content).as_str()) {
        return Err(NativeError::new("RGO-N1-002", FailureClass::Integrity, "RGO-F1 content digest mismatch"));
    }
    let mut units = BTreeSet::new();
    let mut relation_ids = BTreeSet::new();
    for unit in required_array(&logical, "units", "RGO-N1-004")? {
        let id = StableId::new(required_string(unit, "unit_id", "RGO-N1-004")?)?;
        if !id.as_str().starts_with("ruo:unit:") || !units.insert(id) {
            return Err(NativeError::new("RGO-N1-004", FailureClass::Semantic, "invalid or duplicate ReasonGraph Unit ID"));
        }
    }
    for relation in required_array(&logical, "relations", "RGO-N1-004")? {
        let id = StableId::new(required_string(relation, "relation_id", "RGO-N1-004")?)?;
        if !id.as_str().starts_with("ruo:relation:") || !relation_ids.insert(id) {
            return Err(NativeError::new("RGO-N1-004", FailureClass::Semantic, "invalid or duplicate ReasonGraph Relation ID"));
        }
    }
    let known: BTreeSet<StableId> = units.union(&relation_ids).cloned().collect();
    for relation in required_array(&logical, "relations", "RGO-N1-004")? {
        for endpoint_name in ["source", "target"] {
            let endpoint = relation.get(endpoint_name).and_then(Value::as_object)
                .ok_or_else(|| NativeError::new("RGO-N1-004", FailureClass::Semantic, "ReasonGraph endpoint is required"))?;
            let kind = endpoint.get("entity_kind").and_then(Value::as_str);
            let id = StableId::new(endpoint.get("entity_id").and_then(Value::as_str)
                .ok_or_else(|| NativeError::new("RGO-N1-004", FailureClass::Semantic, "ReasonGraph endpoint ID is required"))?)?;
            if !matches!(kind, Some("unit") | Some("relation")) || !known.contains(&id) {
                return Err(NativeError::new("RGO-N1-004", FailureClass::Semantic, "ReasonGraph endpoint does not resolve"));
            }
        }
    }
    Ok(NativeReasonGraph { graph_id, graph_hash, units, relation_ids, logical, canonical_bytes: Some(bytes) })
}

/// Deterministic, read-only queries over a verified native ReasonGraph.
pub fn query_reason_graph(graph: &NativeReasonGraph, query: &str, entity_id: Option<&str>) -> Result<Value, NativeError> {
    if !matches!(query, "summary" | "entity" | "outgoing" | "incoming" | "neighbors") {
        return Err(NativeError::new("RGO-N1-005", FailureClass::Query, "unsupported native ReasonGraph query"));
    }
    let units = required_array(&graph.logical, "units", "RGO-N1-004")?;
    let relations = required_array(&graph.logical, "relations", "RGO-N1-004")?;
    let entity_id = if query == "summary" {
        None
    } else {
        let id = entity_id.ok_or_else(|| NativeError::new("RGO-N1-006", FailureClass::Query, "entity ID is required"))?;
        if !graph.units.iter().any(|value| value.as_str() == id) && !graph.relation_ids.iter().any(|value| value.as_str() == id) {
            return Err(NativeError::new("RGO-N1-006", FailureClass::Query, "entity ID does not resolve in ReasonGraph"));
        }
        Some(id)
    };
    let result = match query {
        "summary" => serde_json::json!({"unit_count": units.len(), "relation_count": relations.len(), "root_refs": graph.logical.get("root_refs").cloned().unwrap_or(Value::Array(Vec::new()))}),
        "entity" => units.iter().chain(relations.iter())
            .find(|entity| entity.get("unit_id").or_else(|| entity.get("relation_id")).and_then(Value::as_str) == entity_id)
            .cloned().ok_or_else(|| NativeError::new("RGO-N1-006", FailureClass::Query, "entity ID does not resolve in ReasonGraph"))?,
        "outgoing" | "incoming" => {
            let endpoint = if query == "outgoing" { "source" } else { "target" };
            Value::Array(relations.iter().filter(|relation| relation.get(endpoint).and_then(Value::as_object).and_then(|value| value.get("entity_id")).and_then(Value::as_str) == entity_id).cloned().collect())
        }
        "neighbors" => {
            let mut adjacent = Vec::new();
            for relation in relations {
                let source = relation.get("source").and_then(Value::as_object).and_then(|value| value.get("entity_id")).and_then(Value::as_str);
                let target = relation.get("target").and_then(Value::as_object).and_then(|value| value.get("entity_id")).and_then(Value::as_str);
                let relation_id = relation.get("relation_id").cloned().ok_or_else(|| NativeError::new("RGO-N1-004", FailureClass::Semantic, "relation ID is required"))?;
                if source == entity_id { adjacent.push(serde_json::json!({"relation_id": relation_id, "direction":"outgoing", "entity_ref": relation.get("target").cloned()})); }
                if target == entity_id { adjacent.push(serde_json::json!({"relation_id": relation_id, "direction":"incoming", "entity_ref": relation.get("source").cloned()})); }
            }
            Value::Array(adjacent)
        }
        _ => unreachable!(),
    };
    Ok(serde_json::json!({"profile": NATIVE_REASON_GRAPH_QUERY_PROFILE, "graph_id": graph.graph_id, "graph_hash": graph.graph_hash, "query": query, "entity_id": entity_id, "read_only": true, "result": result}))
}

/// Atomically apply the safe Phase 16 native graph-update subset.
///
/// The first native mutation boundary accepts only a whole `metadata` map. It
/// therefore preserves all graph identities, references, and lifecycle
/// semantics already verified by RGO-F1 loading while providing native
/// compare-and-commit publication without partial writes.
pub fn transact_reason_graph_file(path: &Path, proposal: &Value, expected_graph_hash: &str, transaction_id: &str) -> Result<Value, NativeError> {
    let graph = load_reason_graph(path)?;
    let _before_bytes = graph.canonical_bytes.clone().ok_or_else(|| NativeError::new("RGO-N1-007", FailureClass::Persistence, "missing canonical graph bytes"))?;
    let rejected = |reason: &str, diagnostic: &str| serde_json::json!({
        "transaction_id": transaction_id, "committed": false, "reason": reason,
        "diagnostic": diagnostic, "partial_commit_count": 0, "graph_hash": graph.graph_hash,
        "source_bytes_unchanged": true,
    });
    if expected_graph_hash != graph.graph_hash {
        return Ok(rejected("stale_graph", "RRG-019"));
    }
    if !transaction_id.starts_with("ruo:transaction:") {
        return Ok(rejected("invalid_transaction_id", "RRG-019"));
    }
    let proposal_object = match proposal.as_object() {
        Some(value) if value.len() == 1 && value.contains_key("graph_updates") => value,
        _ => return Ok(rejected("unknown_proposal_operation", "RRG-020")),
    };
    let updates = match proposal_object.get("graph_updates").and_then(Value::as_object) {
        Some(value) if value.len() == 1 => value,
        _ => return Ok(rejected("invalid_graph_update", "RRG-020")),
    };
    let metadata = match updates.get("metadata").and_then(Value::as_object) {
        Some(value) => Value::Object(value.clone()),
        None => return Ok(rejected("native_phase16_metadata_only", "RRG-020")),
    };
    let mut candidate = graph.logical.clone();
    candidate.as_object_mut().ok_or_else(|| NativeError::new("RGO-N1-004", FailureClass::Semantic, "ReasonGraph must be an object"))?
        .insert("metadata".to_owned(), metadata);
    let payload = encode_reason_graph_bytes(&candidate)?;
    let candidate_hash = sha256(serde_json::to_string(&candidate).map_err(|_| NativeError::new("RGO-N1-007", FailureClass::Persistence, "cannot encode candidate graph"))?.as_bytes());
    let temporary = path.with_file_name(format!(".{}.native-{}", path.file_name().and_then(|name| name.to_str()).unwrap_or("graph.rgraph"), sha256_hex(transaction_id.as_bytes())));
    let write_result = (|| -> Result<(), NativeError> {
        let mut file = OpenOptions::new().create(true).write(true).truncate(true).open(&temporary)
            .map_err(|error| NativeError::new("RGO-N1-007", FailureClass::Persistence, &error.to_string()))?;
        file.write_all(&payload).and_then(|_| file.sync_all())
            .map_err(|error| NativeError::new("RGO-N1-007", FailureClass::Persistence, &error.to_string()))?;
        fs::rename(&temporary, path).map_err(|error| NativeError::new("RGO-N1-007", FailureClass::Persistence, &error.to_string()))
    })();
    if temporary.exists() { let _ = fs::remove_file(&temporary); }
    write_result?;
    Ok(serde_json::json!({
        "transaction_id": transaction_id, "committed": true, "partial_commit_count": 0,
        "before_graph_hash": graph.graph_hash, "graph_hash": candidate_hash,
        "changed_unit_ids": [], "changed_relation_ids": [], "source_bytes_unchanged": false,
        "publication": {"bytes": payload.len(), "sha256": sha256(&payload), "graph_hash": candidate_hash},
        "profile": "reasonscript-reason-object-graph-native-persistence/0.1",
    }))
}

fn encode_reason_graph_bytes(graph: &Value) -> Result<Vec<u8>, NativeError> {
    let graph_id = required_string(graph, "graph_id", "RGO-N1-004")?;
    let header = serde_json::json!({"magic":"REASONGRAPH-F1", "format_version":"1.0", "canonicalization_profile":"reason-object-graph-canonical-jsonl/1", "logical_model":"mra-reason-object-graph/0.1", "media_type":"application/vnd.reasonscript.reason-graph+jsonl", "graph_id":graph_id});
    let header_record = envelope("file_header", &header, 0)?;
    let graph_record = envelope("graph", graph, 1)?;
    let mut content = Vec::new();
    content.extend(serde_json::to_vec(&header_record).map_err(|_| NativeError::new("RGO-N1-007", FailureClass::Persistence, "cannot encode RGO-F1 header"))?); content.push(b'\n');
    content.extend(serde_json::to_vec(&graph_record).map_err(|_| NativeError::new("RGO-N1-007", FailureClass::Persistence, "cannot encode RGO-F1 graph"))?); content.push(b'\n');
    let seal = serde_json::json!({"format_version":"1.0", "graph_id":graph_id, "graph_hash":sha256(serde_json::to_string(graph).map_err(|_| NativeError::new("RGO-N1-007", FailureClass::Persistence, "cannot hash RGO-F1 graph"))?.as_bytes()), "content_stream_sha256":sha256(&content), "content_record_count":2, "total_record_count":3});
    let seal_record = envelope("file_seal", &seal, 2)?;
    content.extend(serde_json::to_vec(&seal_record).map_err(|_| NativeError::new("RGO-N1-007", FailureClass::Persistence, "cannot encode RGO-F1 seal"))?); content.push(b'\n');
    Ok(content)
}

fn envelope(record_type: &str, body: &Value, ordinal: u64) -> Result<Value, NativeError> {
    let body_bytes = serde_json::to_vec(body).map_err(|_| NativeError::new("RGO-N1-007", FailureClass::Persistence, "cannot encode RGO-F1 record"))?;
    Ok(serde_json::json!({"record_type":record_type, "record_version":"1.0", "ordinal":ordinal, "body":body, "body_sha256":sha256(&body_bytes)}))
}

fn required_string<'a>(value: &'a Value, key: &str, code: &str) -> Result<&'a str, NativeError> {
    value.get(key).and_then(Value::as_str).ok_or_else(|| NativeError::new(code, FailureClass::Semantic, "required string is missing"))
}

fn required_array<'a>(value: &'a Value, key: &str, code: &str) -> Result<&'a Vec<Value>, NativeError> {
    value.get(key).and_then(Value::as_array).ok_or_else(|| NativeError::new(code, FailureClass::Semantic, "required array is missing"))
}

fn string_at(value: &Value, path: &[&str]) -> Result<String, NativeError> {
    let mut cursor = value;
    for key in path {
        cursor = cursor
            .get(*key)
            .ok_or_else(|| NativeError::semantic("required identity missing"))?;
    }
    cursor
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| NativeError::semantic("identity must be a string"))
}
fn sha256(data: &[u8]) -> String {
    format!("sha256:{}", sha256_hex(data))
}
fn sha256_hex(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FailureClass {
    Load,
    Integrity,
    Compatibility,
    Semantic,
    Resource,
    StaleHandle,
    Conflict,
    Lifecycle,
    Query,
    Projection,
    Persistence,
    Limit,
    Adapter,
    InternalInvariant,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct NativeError {
    pub code: String,
    pub class: FailureClass,
    pub message: String,
}
impl NativeError {
    fn new(code: &str, class: FailureClass, message: &str) -> Self {
        Self {
            code: code.into(),
            class,
            message: message.into(),
        }
    }
    fn semantic(message: &str) -> Self {
        Self::new("RUO-N1-005", FailureClass::Semantic, message)
    }
    fn stale() -> Self {
        Self::new(
            "RUO-N1-004",
            FailureClass::StaleHandle,
            "stale, wrong-generation, or cross-store handle",
        )
    }
    fn internal(message: &str) -> Self {
        Self::new("RUO-N1-020", FailureClass::InternalInvariant, message)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn object() -> NativeReasonUnitObject {
        NativeReasonUnitObject::from_logical(serde_json::json!({"object_identity":{"entity_id":"ruo:object:test"},"current_revision":"ruo:revision:1","root_units":["ruo:unit:root"],"units":[{"entity_id":"ruo:unit:root","owner_id":"ruo:object:test","unit_kind":"atomic"}],"payloads":[],"states":[],"relations":[],"constraints":[],"evidence_registry":[],"revisions":[{"revision_id":"ruo:revision:1"}],"extension_registry":[],"projection_descriptors":[]})).unwrap()
    }
    #[test]
    fn stable_identity_and_generation_checked_handles() {
        let store = NativeObjectStore::new(7, 100);
        let first = store.insert_object(object()).unwrap();
        let id = StableId::new("ruo:unit:root").unwrap();
        let handle = store.resolve_id(&first, &id).unwrap();
        assert_eq!(store.resolve_handle(&first, handle).unwrap().id, id);
        let tx = store.begin_transaction(&first, StableId::new("ruo:transaction:1").unwrap());
        let next = store.commit_transaction(tx).unwrap();
        assert_eq!(
            store.resolve_handle(&next, handle).unwrap_err().class,
            FailureClass::StaleHandle
        );
    }
    #[test]
    fn snapshot_is_immutable_and_conflict_is_atomic() {
        let store = NativeObjectStore::new(8, 100);
        let first = store.insert_object(object()).unwrap();
        let tx1 = store.begin_transaction(&first, StableId::new("ruo:transaction:1").unwrap());
        let tx2 = store.begin_transaction(&first, StableId::new("ruo:transaction:2").unwrap());
        let next = store.commit_transaction(tx1).unwrap();
        assert_ne!(first.generation, next.generation);
        assert_eq!(first.revision_id.as_str(), "ruo:revision:1");
        assert_eq!(
            store.commit_transaction(tx2).unwrap_err().class,
            FailureClass::Conflict
        );
        assert_eq!(
            store.snapshot(&first.object_id).unwrap().generation,
            next.generation
        );
    }
    #[test]
    fn deterministic_registry_query_and_projection() {
        let store = NativeObjectStore::new(9, 100);
        let snapshot = store.insert_object(object()).unwrap();
        let ids: Vec<_> = snapshot
            .query(NativeQuery::All)
            .into_iter()
            .map(|e| e.id)
            .collect();
        assert!(ids.windows(2).all(|pair| pair[0] < pair[1]));
        let projection = snapshot.project_execution(&[]).unwrap();
        assert_eq!(projection.owner_id, snapshot.object_id);
    }
    #[test]
    fn invalid_owner_rolls_back() {
        let store = NativeObjectStore::new(10, 100);
        let snapshot = store.insert_object(object()).unwrap();
        let mut tx =
            store.begin_transaction(&snapshot, StableId::new("ruo:transaction:bad").unwrap());
        tx.operations
            .push(TransactionOperation::Upsert(NativeEntity {
                id: StableId::new("ruo:payload:x").unwrap(),
                owner_id: StableId::new("ruo:object:other").unwrap(),
                kind: EntityKind::Payload,
                revision: 1,
                load_state: LoadState::Materialized,
                execution_eligible: true,
                value: Value::Null,
            }));
        assert!(store.commit_transaction(tx).is_err());
        assert_eq!(
            store.snapshot(&snapshot.object_id).unwrap().generation,
            snapshot.generation
        );
    }
    #[test]
    fn public_snapshot_is_send_sync() {
        fn assert_send_sync<T: Send + Sync>() {}
        assert_send_sync::<NativeSnapshot>();
        assert_send_sync::<NativeObjectStore>();
    }
}
