//! Native ReasonUnit Object runtime core (RUO-N1).
//!
//! The core deliberately uses ordered collections and safe Rust only. Stable
//! semantic identity never depends on an address, slot, worker, or tensor index.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;
use std::sync::{Arc, RwLock};

pub const PROFILE: &str = "reasonscript-reasonunit-native-runtime/1.0";

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
        let envelope: Value = serde_json::from_slice(line).map_err(|_| {
            NativeError::new(
                "RUO-N1-007",
                FailureClass::Integrity,
                "invalid JSONL record",
            )
        })?;
        let body = envelope.get("body").ok_or_else(|| {
            NativeError::new("RUO-N1-007", FailureClass::Integrity, "record body missing")
        })?;
        let body_bytes = serde_json::to_vec(body)
            .map_err(|_| NativeError::internal("record encoding failed"))?;
        if envelope.get("body_sha256").and_then(Value::as_str)
            != Some(sha256_hex(&body_bytes).as_str())
        {
            return Err(NativeError::new(
                "RUO-N1-007",
                FailureClass::Integrity,
                "record digest mismatch",
            ));
        }
        match envelope.get("record_type").and_then(Value::as_str) {
            Some("object") => logical_object = Some(body.clone()),
            Some("file_seal") => {
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
