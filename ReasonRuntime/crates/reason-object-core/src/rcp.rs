//! RCP Foundation: lossless, bounded, deterministic local Domain DSN transport.
use crate::{NativeReasonUnitObject, StableId};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

pub const UNKNOWN_STRUCTURE_PROFILE: &str = "reasonscript-unknown-structure/0.1";
pub const VERSION: &str = "0.2";
pub const SCHEMA: &str = "reasonscript-rcp-message/0.2";
pub type RCPResult<T> = Result<T, String>;
fn reject<T>(reason: &str) -> RCPResult<T> {
    Err(format!("RCP-001: {reason}"))
}
fn identity(id: &str) -> RCPResult<()> {
    StableId::new(id)
        .map(|_| ())
        .map_err(|_| format!("RCP-001: invalid identity {id}"))
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RCPKind {
    Request,
    Result,
    UnknownReport,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ReferenceKind {
    RU,
    RUS,
    RUO,
    Relation,
    Evidence,
    Knowledge,
    ExecutionState,
    ExecutionBinding,
    ExecutionRelation,
    NativeObject,
    URU,
    URUS,
    URUO,
    UnknownRelation,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RCPReference {
    pub kind: ReferenceKind,
    pub id: String,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RCPRecord {
    pub reference: RCPReference,
    pub value: Value,
    pub references: Vec<RCPReference>,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RCPPayload {
    pub records: Vec<RCPRecord>,
    pub unknowns: Vec<UnknownUnit>,
}
impl RCPPayload {
    /// Required profiles are derived from typed references, never trusted sender claims.
    pub fn required_profiles(&self) -> BTreeSet<String> {
        let extended = |r: &RCPReference| {
            matches!(
                r.kind,
                ReferenceKind::URU
                    | ReferenceKind::URUS
                    | ReferenceKind::URUO
                    | ReferenceKind::UnknownRelation
            )
        };
        if self
            .records
            .iter()
            .any(|r| extended(&r.reference) || r.references.iter().any(extended))
            || self.unknowns.iter().any(|u| {
                u.origins
                    .iter()
                    .chain(&u.grounds)
                    .chain(u.history.iter().flat_map(|h| &h.evidence))
                    .any(extended)
            })
        {
            BTreeSet::from([UNKNOWN_STRUCTURE_PROFILE.to_string()])
        } else {
            BTreeSet::new()
        }
    }
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RCPMessage {
    pub schema: String,
    pub protocol_version: String,
    pub message_id: String,
    pub source: String,
    pub destination: String,
    pub kind: RCPKind,
    pub correlation_id: String,
    pub causation_id: Option<String>,
    pub trace: Vec<String>,
    pub payload: RCPPayload,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum UnknownCause {
    MissingKnowledge,
    MissingEvidence,
    Ambiguous,
    Conflict,
    Dependency,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum UnknownState {
    Open,
    InProgress,
    Candidate,
    Resolved,
    Reopened,
    Blocked,
}
impl UnknownState {
    /// Protocol edges only; retry, invalidation and limit decisions belong to .rsn.
    fn permits(&self, next: &Self) -> bool {
        matches!(
            (self, next),
            (Self::Open, Self::InProgress | Self::Blocked)
                | (
                    Self::InProgress,
                    Self::Candidate | Self::Open | Self::Blocked
                )
                | (Self::Candidate, Self::Resolved | Self::Open)
                | (Self::Resolved, Self::Reopened)
                | (Self::Reopened, Self::Open)
        )
    }
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownRevision {
    pub state: UnknownState,
    pub evidence: Vec<RCPReference>,
    pub candidate: Option<Value>,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownUnit {
    pub id: String,
    pub origins: Vec<RCPReference>,
    pub cause: UnknownCause,
    pub grounds: Vec<RCPReference>,
    pub dependencies: Vec<String>,
    pub history: Vec<UnknownRevision>,
}
impl UnknownUnit {
    pub fn state(&self) -> Option<&UnknownState> {
        self.history.last().map(|r| &r.state)
    }
    pub fn validate(&self) -> RCPResult<()> {
        identity(&self.id)?;
        if self.origins.iter().any(|origin| origin.id == self.id) {
            return reject("UNKNOWN identity must differ from origins");
        }
        if self.origins.is_empty()
            || self.origins.iter().any(|r| {
                !matches!(
                    r.kind,
                    ReferenceKind::RU | ReferenceKind::RUS | ReferenceKind::RUO
                )
            })
        {
            return reject("UNKNOWN needs RU/RUS/RUO origins");
        }
        if self.history.first().map(|revision| &revision.state) != Some(&UnknownState::Open) {
            return reject("UNKNOWN history must begin OPEN");
        }
        for (index, revision) in self.history.iter().enumerate() {
            if index > 0 && !self.history[index - 1].state.permits(&revision.state) {
                return reject("invalid UNKNOWN transition");
            }
            if revision
                .evidence
                .iter()
                .any(|r| r.kind != ReferenceKind::Evidence)
            {
                return reject("candidate evidence has wrong kind");
            }
            if matches!(
                revision.state,
                UnknownState::Candidate | UnknownState::Resolved
            ) {
                if revision.candidate.is_none() || revision.evidence.is_empty() {
                    return reject("candidate requires value and evidence");
                }
                if revision.state == UnknownState::Resolved
                    && self.history[index - 1].candidate != revision.candidate
                {
                    return reject("resolved candidate changed");
                }
            } else if revision.candidate.is_some() {
                return reject("candidate outside candidate/resolution revision");
            }
        }
        for r in self
            .origins
            .iter()
            .chain(&self.grounds)
            .chain(self.history.iter().flat_map(|r| &r.evidence))
        {
            identity(&r.id)?;
        }
        Ok(())
    }
}

/// The evaluator is supplied by the domain; dispatch never solves UNKNOWNs.
pub trait CandidateValidator {
    fn validate(&self, unit: &UnknownUnit, candidate: &Value) -> RCPResult<()>;
}
#[derive(Default)]
pub struct UnknownRegistry {
    pub(crate) units: BTreeMap<String, UnknownUnit>,
}
impl UnknownRegistry {
    pub fn get(&self, id: &str) -> Option<&UnknownUnit> {
        self.units.get(id)
    }
    /// Commit a .rsn-produced revision while preserving the immutable origin and journal.
    pub fn commit(
        &mut self,
        unit: UnknownUnit,
        context: &RCPPayload,
        validator: &dyn CandidateValidator,
    ) -> RCPResult<()> {
        unit.validate()?;
        context.validate()?;
        if context.records.iter().any(|record| {
            record.reference.id == unit.id && record.reference.kind != ReferenceKind::URU
        }) {
            return reject("UNKNOWN identity collides with another record kind");
        }
        for reference in unit
            .origins
            .iter()
            .chain(&unit.grounds)
            .chain(unit.history.iter().flat_map(|r| &r.evidence))
        {
            let present = if reference.kind == ReferenceKind::URU {
                context.unknowns.iter().any(|unit| unit.id == reference.id)
            } else {
                context
                    .records
                    .iter()
                    .any(|record| record.reference == *reference)
            };
            if !present {
                return reject("UNKNOWN reference missing from context");
            }
        }
        for dependency in &unit.dependencies {
            if dependency == &unit.id || !self.units.contains_key(dependency) {
                return reject("unregistered UNKNOWN dependency");
            }
        }
        match self.units.get(&unit.id) {
            None if unit.history.len() != 1 => return reject("new UNKNOWN must be OPEN"),
            Some(previous) => {
                let mut expected = previous.clone();
                if unit.history.len() != previous.history.len() + 1 {
                    return reject("UNKNOWN revision conflict");
                }
                expected.history.push(unit.history.last().unwrap().clone());
                if expected != unit {
                    return reject("UNKNOWN origin or history mutation");
                }
            }
            _ => {}
        }
        if matches!(
            unit.state(),
            Some(UnknownState::Candidate | UnknownState::Resolved)
        ) {
            validator.validate(
                &unit,
                unit.history.last().unwrap().candidate.as_ref().unwrap(),
            )?;
        }
        if unit.state() == Some(&UnknownState::Resolved)
            && unit
                .dependencies
                .iter()
                .any(|id| self.units[id].state() != Some(&UnknownState::Resolved))
        {
            return reject("unresolved UNKNOWN dependency");
        }
        if unit.state() != Some(&UnknownState::Resolved)
            && self.units.values().any(|dependent| {
                dependent.state() == Some(&UnknownState::Resolved)
                    && dependent.dependencies.contains(&unit.id)
            })
        {
            return reject("reopen resolved dependents before their dependency");
        }
        self.units.insert(unit.id.clone(), unit);
        Ok(())
    }
}

impl RCPPayload {
    pub fn validate(&self) -> RCPResult<()> {
        // UNKNOWN bodies are the authoritative URU identities, including when
        // an optional URU information record describes that same identity.
        let mut unknowns = BTreeMap::new();
        for unit in &self.unknowns {
            unit.validate()?;
            if unknowns.insert(unit.id.clone(), unit).is_some() {
                return reject("duplicate UNKNOWN identity");
            }
        }
        let mut index = BTreeMap::new();
        for record in &self.records {
            identity(&record.reference.id)?;
            if !record.value.is_object() {
                return reject("record body must be an object");
            }
            if index.insert(record.reference.id.as_str(), record).is_some() {
                return reject("duplicate record identity");
            }
            if record.value.get("id").and_then(Value::as_str) != Some(&record.reference.id) {
                return reject("record identity mismatch");
            }
        }
        let check = |reference: &RCPReference| -> RCPResult<()> {
            if reference.kind == ReferenceKind::URU {
                return if unknowns.contains_key(&reference.id) {
                    Ok(())
                } else {
                    reject("dangling URU reference")
                };
            }
            if index.get(reference.id.as_str()).map(|r| &r.reference.kind) != Some(&reference.kind)
            {
                return reject("dangling or mistyped reference");
            }
            Ok(())
        };
        for record in &self.records {
            crate::structure::validate_record(&index, record)?;
            crate::unknown_structure::validate_record(&index, &unknowns, record)?;
            for reference in &record.references {
                check(reference)?;
            }
            if let Some(logical) = record.value.get("native_logical") {
                if record.reference.kind != ReferenceKind::NativeObject {
                    return reject(
                        "native logical body requires an explicit native container kind",
                    );
                }
                let object = NativeReasonUnitObject::from_logical(logical.clone())
                    .map_err(|e| format!("RCP-001: {}", e.message))?;
                if object.object_id.as_str() != record.reference.id
                    || !object.entities.contains_key(&object.revision_id)
                {
                    return reject("native object identity or revision mismatch");
                }
                for entity in object.entities.values() {
                    if entity.owner_id != object.object_id
                        && !object.entities.contains_key(&entity.owner_id)
                    {
                        return reject("native owner missing");
                    }
                }
                validate_native_references(logical, &object)?;
            }
            // Validate embedded runtime references as well as the transport manifest.
            for (key, value) in record.value.as_object().unwrap() {
                let kind = match key.as_str() {
                    "execution_state_ref" => Some(ReferenceKind::ExecutionState),
                    "reason_unit_ref" | "source_ru" => Some(ReferenceKind::RU),
                    "evidence_refs" => Some(ReferenceKind::Evidence),
                    "execution_relation_refs" => Some(ReferenceKind::ExecutionRelation),
                    "relation_refs" => Some(if record.reference.kind == ReferenceKind::URUS {
                        ReferenceKind::UnknownRelation
                    } else {
                        ReferenceKind::Relation
                    }),
                    "uru_refs" => Some(ReferenceKind::URU),
                    "urus_refs" => Some(ReferenceKind::URUS),
                    "ruo_refs" => Some(ReferenceKind::RUO),
                    "unit_refs" => Some(ReferenceKind::RU),
                    "structure_refs" => Some(ReferenceKind::RUS),
                    "knowledge_refs" => Some(ReferenceKind::Knowledge),
                    "source_ref" | "target_ref" => None,
                    _ => continue,
                };
                if value.is_null() {
                    continue;
                }
                let values = if let Some(array) = value.as_array() {
                    array.clone()
                } else {
                    vec![value.clone()]
                };
                for id in values {
                    let id = id.as_str().ok_or("RCP-001: reference must be a string")?;
                    let actual = if unknowns.contains_key(id) {
                        &ReferenceKind::URU
                    } else {
                        &index
                            .get(id)
                            .ok_or("RCP-001: dangling embedded reference")?
                            .reference
                            .kind
                    };
                    if kind.as_ref().is_some_and(|kind| kind != actual) {
                        return reject("mistyped embedded reference");
                    }
                    if !record.references.contains(&RCPReference {
                        id: id.into(),
                        kind: actual.clone(),
                    }) {
                        return reject("embedded reference missing from manifest");
                    }
                }
            }
        }
        for unit in &self.unknowns {
            if index
                .get(unit.id.as_str())
                .is_some_and(|record| record.reference.kind != ReferenceKind::URU)
            {
                return reject("UNKNOWN identity collides with another record kind");
            }
            for r in unit
                .origins
                .iter()
                .chain(&unit.grounds)
                .chain(unit.history.iter().flat_map(|h| &h.evidence))
            {
                check(r)?;
            }
        }
        // Iterative traversal keeps long dependency chains off the call stack.
        let mut pending: BTreeMap<String, usize> = BTreeMap::new();
        let mut dependents: BTreeMap<String, Vec<String>> = BTreeMap::new();
        let mut ready = BTreeSet::new();
        for (id, unit) in &unknowns {
            pending.insert(id.clone(), unit.dependencies.len());
            if unit.dependencies.is_empty() {
                ready.insert(id.clone());
            }
            for dependency in &unit.dependencies {
                if !unknowns.contains_key(dependency) {
                    return reject("dangling UNKNOWN dependency");
                }
                dependents
                    .entry(dependency.clone())
                    .or_default()
                    .push(id.clone());
            }
        }
        for unit in unknowns.values() {
            if unit.state() == Some(&UnknownState::Resolved)
                && unit
                    .dependencies
                    .iter()
                    .any(|id| unknowns[id].state() != Some(&UnknownState::Resolved))
            {
                return reject("resolved UNKNOWN has unresolved dependency");
            }
        }
        let mut visited = 0;
        while let Some(id) = ready.pop_first() {
            visited += 1;
            if let Some(children) = dependents.get(&id) {
                for child in children {
                    let count = pending.get_mut(child).unwrap();
                    *count -= 1;
                    if *count == 0 {
                        ready.insert(child.clone());
                    }
                }
            }
        }
        if visited != unknowns.len() {
            return reject("cyclic UNKNOWN dependency");
        }
        Ok(())
    }
    /// Transport the current structural trace without legacy state/object coercions.
    pub fn from_runtime_trace(trace: &Value) -> RCPResult<Self> {
        if trace.get("schema").and_then(Value::as_str) != Some(crate::structure::TRACE_SCHEMA) {
            return reject("unsupported structural runtime trace");
        }
        let fields = trace
            .as_object()
            .ok_or("RCP-001: structural trace must be an object")?;
        let allowed = [
            "schema",
            "mode",
            "hashes",
            "reason_units",
            "reason_structures",
            "spatial_objects",
            "relations",
            "evidence",
            "execution_states",
            "execution_bindings",
            "execution_relations",
        ];
        if fields.keys().any(|key| !allowed.contains(&key.as_str())) {
            return reject("unsupported structural trace field");
        }
        if let Some(mode) = trace.get("mode") {
            if !matches!(mode.as_str(), Some("off" | "ru" | "rus" | "rus_with_state")) {
                return reject("unsupported structural trace mode");
            }
        }
        let mut payload = Self {
            records: vec![],
            unknowns: vec![],
        };
        for (section, kind) in [
            ("reason_units", ReferenceKind::RU),
            ("reason_structures", ReferenceKind::RUS),
            ("spatial_objects", ReferenceKind::RUO),
            ("relations", ReferenceKind::Relation),
            ("evidence", ReferenceKind::Evidence),
            ("execution_states", ReferenceKind::ExecutionState),
            ("execution_bindings", ReferenceKind::ExecutionBinding),
            ("execution_relations", ReferenceKind::ExecutionRelation),
        ] {
            let values = trace
                .get(section)
                .and_then(Value::as_array)
                .ok_or("RCP-001: missing structural trace section")?;
            for value in values {
                let id = value
                    .get("id")
                    .and_then(Value::as_str)
                    .ok_or("RCP-001: missing structural identity")?;
                payload.records.push(RCPRecord {
                    reference: RCPReference {
                        kind: kind.clone(),
                        id: id.into(),
                    },
                    value: value.clone(),
                    references: vec![],
                });
            }
        }
        let index: BTreeMap<_, _> = payload
            .records
            .iter()
            .map(|r| (r.reference.id.clone(), r.reference.kind.clone()))
            .collect();
        for record in &mut payload.records {
            for key in [
                "execution_state_ref",
                "execution_relation_refs",
                "reason_unit_ref",
                "source_ru",
                "source_ref",
                "target_ref",
                "evidence_refs",
                "relation_refs",
                "knowledge_refs",
                "unit_refs",
                "structure_refs",
            ] {
                if let Some(value) = record.value.get(key) {
                    if value.is_null() {
                        continue;
                    }
                    let values = value
                        .as_array()
                        .cloned()
                        .unwrap_or_else(|| vec![value.clone()]);
                    for value in values {
                        let id = value
                            .as_str()
                            .ok_or("RCP-001: invalid structural reference")?;
                        let kind = index.get(id).ok_or("RCP-001: missing structural target")?;
                        record.references.push(RCPReference {
                            kind: kind.clone(),
                            id: id.into(),
                        });
                    }
                }
            }
        }
        payload.validate()?;
        Ok(payload)
    }
    pub fn from_native_object(object: &NativeReasonUnitObject) -> RCPResult<Self> {
        // Preserve the complete canonical logical object, not opaque runtime handles.
        let value =
            serde_json::json!({"id": object.object_id.as_str(), "native_logical": object.logical});
        let payload = Self {
            records: vec![RCPRecord {
                reference: RCPReference {
                    kind: ReferenceKind::NativeObject,
                    id: object.object_id.as_str().into(),
                },
                value,
                references: vec![],
            }],
            unknowns: vec![],
        };
        payload.validate()?;
        Ok(payload)
    }
    pub fn native_object(&self, id: &str) -> RCPResult<NativeReasonUnitObject> {
        self.validate()?;
        let record = self
            .records
            .iter()
            .find(|r| r.reference.id == id && r.reference.kind == ReferenceKind::NativeObject)
            .ok_or("RCP-001: native RUO missing")?;
        NativeReasonUnitObject::from_logical(
            record
                .value
                .get("native_logical")
                .ok_or("RCP-001: native logical object missing")?
                .clone(),
        )
        .map_err(|e| format!("RCP-001: {}", e.message))
    }
}

impl RCPMessage {
    pub fn validate(&self) -> RCPResult<()> {
        if self.schema != SCHEMA || self.protocol_version != VERSION {
            return reject("unsupported schema or protocol version");
        }
        for id in [
            &self.message_id,
            &self.source,
            &self.destination,
            &self.correlation_id,
        ] {
            identity(id)?;
        }
        if let Some(id) = &self.causation_id {
            identity(id)?;
            if id == &self.message_id {
                return reject("self causation");
            }
        }
        if self.kind == RCPKind::Result && self.causation_id.is_none() {
            return reject("RESULT requires causation");
        }
        if self.kind == RCPKind::UnknownReport && self.payload.unknowns.is_empty() {
            return reject("UNKNOWN_REPORT requires UNKNOWN");
        }
        let mut visited = BTreeSet::new();
        for core in &self.trace {
            identity(core)?;
            if !visited.insert(core) {
                return reject("cyclic trace");
            }
        }
        if !self.trace.is_empty() && self.trace.last() != Some(&self.source) {
            return reject("trace source mismatch");
        }
        if (self.trace.contains(&self.destination)
            && !(self.kind == RCPKind::Result
                && self.trace.len() >= 2
                && self.trace.get(self.trace.len() - 2) == Some(&self.destination)))
            || self.source == self.destination
        {
            return reject("cyclic delivery");
        }
        if self.payload.records.is_empty() {
            return reject("empty reasoning payload");
        }
        self.payload.validate()
    }
    pub fn encode(&self) -> RCPResult<Vec<u8>> {
        self.validate()?;
        serde_json::to_value(self)
            .and_then(|value| serde_json::to_vec(&canonical(value)))
            .map_err(|e| format!("RCP-001: {e}"))
    }
    pub fn decode(bytes: &[u8], max_bytes: usize) -> RCPResult<Self> {
        if bytes.len() > max_bytes {
            return reject("message byte limit");
        }
        let message: Self = serde_json::from_slice(bytes).map_err(|e| format!("RCP-001: {e}"))?;
        message.validate()?;
        Ok(message)
    }
}

#[derive(Clone, Debug)]
pub struct RCPLimits {
    pub messages: usize,
    pub requests: usize,
    pub hops: usize,
    pub bytes: usize,
}
pub struct RCPRouter {
    cores: BTreeMap<String, String>,
    profiles: BTreeMap<String, BTreeSet<String>>,
}
impl Default for RCPRouter {
    fn default() -> Self {
        Self {
            cores: BTreeMap::new(),
            profiles: BTreeMap::new(),
        }
    }
}
impl RCPRouter {
    pub fn register(&mut self, domain_dsn: String, core_id: String) -> RCPResult<()> {
        self.register_with_profiles(domain_dsn, core_id, BTreeSet::new())
    }
    pub fn register_with_profiles(
        &mut self,
        domain_dsn: String,
        core_id: String,
        profiles: BTreeSet<String>,
    ) -> RCPResult<()> {
        identity(&domain_dsn)?;
        identity(&core_id)?;
        if profiles.iter().any(|p| p != UNKNOWN_STRUCTURE_PROFILE) {
            return reject("unsupported receiver profile");
        }
        if self.cores.contains_key(&domain_dsn) || self.cores.values().any(|id| id == &core_id) {
            return reject("duplicate Domain DSN or core");
        }
        self.profiles.insert(domain_dsn.clone(), profiles);
        self.cores.insert(domain_dsn, core_id);
        Ok(())
    }
    /// Sender preflight; dispatch repeats this check before any delivery mutation.
    pub fn check_profiles(&self, destination: &str, payload: &RCPPayload) -> RCPResult<()> {
        self.resolve(destination)?;
        if !payload
            .required_profiles()
            .is_subset(&self.profiles[destination])
        {
            return reject("receiver does not support required structure profile");
        }
        Ok(())
    }
    pub fn resolve(&self, domain_dsn: &str) -> RCPResult<&str> {
        self.cores
            .get(domain_dsn)
            .map(String::as_str)
            .ok_or("RCP-001: unregistered Domain DSN".into())
    }
}
pub struct RCPDispatcher {
    pub router: RCPRouter,
    limits: RCPLimits,
    delivered: BTreeMap<String, RCPMessage>,
    inboxes: BTreeMap<String, Vec<RCPMessage>>,
    requests: usize,
}
impl RCPDispatcher {
    pub fn new(limits: RCPLimits) -> Self {
        Self {
            router: RCPRouter::default(),
            limits,
            delivered: BTreeMap::new(),
            inboxes: BTreeMap::new(),
            requests: 0,
        }
    }
    pub fn dispatch(&mut self, bytes: &[u8]) -> RCPResult<()> {
        let mut message = RCPMessage::decode(bytes, self.limits.bytes)?;
        self.router.resolve(&message.source)?;
        self.router
            .check_profiles(&message.destination, &message.payload)?;
        for dsn in &message.trace {
            self.router.resolve(dsn)?;
        }
        if self.delivered.contains_key(&message.message_id) {
            return reject("duplicate message");
        }
        if self.delivered.len() >= self.limits.messages
            || message.trace.len().max(1) + 1 > self.limits.hops
        {
            return reject("communication limit");
        }
        if message.kind == RCPKind::Request && self.requests >= self.limits.requests {
            return reject("reasoning request limit");
        }
        if let Some(parent_id) = &message.causation_id {
            let parent = self
                .delivered
                .get(parent_id)
                .ok_or("RCP-001: unknown causation")?;
            if parent.destination != message.source
                || parent.correlation_id != message.correlation_id
                || parent.protocol_version != message.protocol_version
                || message.trace != parent.trace
            {
                return reject("causal route mismatch");
            }
            // A direct RESULT may return to the requester; forwarding REQUESTs may not.
            if message.kind == RCPKind::Result
                && (parent.kind != RCPKind::Request || parent.source != message.destination)
            {
                return reject("RESULT does not answer REQUEST");
            }
        } else if message.kind == RCPKind::Result {
            return reject("RESULT requires a delivered REQUEST");
        } else if !message.trace.is_empty() {
            return reject("root message carries forged trace");
        }
        if message.trace.is_empty() {
            message.trace.push(message.source.clone());
        }
        message.trace.push(message.destination.clone());
        if message.kind == RCPKind::Request {
            self.requests += 1;
        }
        self.delivered
            .insert(message.message_id.clone(), message.clone());
        self.inboxes
            .entry(message.destination.clone())
            .or_default()
            .push(message);
        Ok(())
    }
    pub fn receive(&mut self, domain_dsn: &str) -> RCPResult<Vec<RCPMessage>> {
        self.router.resolve(domain_dsn)?;
        Ok(self.inboxes.remove(domain_dsn).unwrap_or_default())
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RCPSession {
    pub cores: BTreeMap<String, String>,
    #[serde(default)]
    pub profiles: BTreeMap<String, BTreeSet<String>>,
    pub limits: RCPSessionLimits,
    pub messages: Vec<RCPMessage>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RCPSessionLimits {
    pub messages: usize,
    pub requests: usize,
    pub hops: usize,
    pub bytes: usize,
}
/// Bounded native I/O adapter. Domains construct/evaluate payloads in .rsn.
pub fn run_session(session: RCPSession) -> RCPResult<Value> {
    let mut dispatcher = RCPDispatcher::new(RCPLimits {
        messages: session.limits.messages,
        requests: session.limits.requests,
        hops: session.limits.hops,
        bytes: session.limits.bytes,
    });
    if session
        .profiles
        .keys()
        .any(|dsn| !session.cores.contains_key(dsn))
    {
        return reject("profile declaration for unregistered Domain DSN");
    }
    for (dsn, core) in &session.cores {
        dispatcher.router.register_with_profiles(
            dsn.clone(),
            core.clone(),
            session.profiles.get(dsn).cloned().unwrap_or_default(),
        )?;
    }
    for message in session.messages {
        dispatcher.dispatch(&message.encode()?)?;
    }
    let mut deliveries = BTreeMap::new();
    for dsn in session.cores.keys() {
        deliveries.insert(dsn, dispatcher.receive(dsn)?);
    }
    Ok(
        serde_json::json!({"schema":"reasonscript-rcp-session/0.1", "ok":true, "deliveries":deliveries}),
    )
}

fn canonical(value: Value) -> Value {
    match value {
        Value::Object(values) => {
            let ordered: BTreeMap<_, _> =
                values.into_iter().map(|(k, v)| (k, canonical(v))).collect();
            Value::Object(ordered.into_iter().collect())
        }
        Value::Array(values) => Value::Array(values.into_iter().map(canonical).collect()),
        other => other,
    }
}

fn validate_native_references(value: &Value, object: &NativeReasonUnitObject) -> RCPResult<()> {
    match value {
        Value::Object(fields) => {
            for (key, value) in fields {
                if matches!(
                    key.as_str(),
                    "root_units"
                        | "children"
                        | "owner_object_id"
                        | "source_id"
                        | "target_id"
                        | "unit_refs"
                        | "evidence_refs"
                        | "relation_refs"
                        | "payload_ref"
                        | "state_ref"
                        | "current_revision"
                        | "owner_id"
                        | "source_unit_ref"
                        | "target_unit_ref"
                ) {
                    let values = value
                        .as_array()
                        .cloned()
                        .unwrap_or_else(|| vec![value.clone()]);
                    for value in values {
                        if value.is_null() {
                            continue;
                        }
                        let id = value.as_str().ok_or("RCP-001: invalid native reference")?;
                        if id != object.object_id.as_str()
                            && !object.entities.keys().any(|key| key.as_str() == id)
                        {
                            return reject("dangling native reference");
                        }
                    }
                } else {
                    validate_native_references(value, object)?;
                }
            }
        }
        Value::Array(values) => {
            for value in values {
                validate_native_references(value, object)?;
            }
        }
        _ => {}
    }
    Ok(())
}
