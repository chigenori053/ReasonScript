//! RU/RUS/RUO Structural Definition v0.1. Runtime snapshots are separate kinds.
use crate::rcp::{RCPRecord, RCPReference, ReferenceKind};
use crate::StableId;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

pub const TRACE_SCHEMA: &str = "reasonscript-reason-structure-trace/0.1";
pub const PROFILE: &str = "reasonscript-reasoning-structure/0.1";
type Result<T> = std::result::Result<T, String>;
fn error<T>(message: &str) -> Result<T> {
    Err(format!("RCP-STRUCT-001: {message}"))
}
fn id(value: &str) -> Result<()> {
    StableId::new(value)
        .map(|_| ())
        .map_err(|_| format!("RCP-STRUCT-001: invalid identity {value}"))
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReasonUnit {
    pub id: String,
    pub kind: String,
    pub content: Value,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReasonUnitStructure {
    pub id: String,
    pub unit_refs: Vec<String>,
    pub relation_refs: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum RelationDomain {
    #[serde(rename = "non_spatial")]
    NonSpatial,
    #[serde(rename = "spatial_3d")]
    Spatial3D,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReasonRelation {
    pub id: String,
    pub domain: RelationDomain,
    pub kind: String,
    pub source_ref: String,
    pub target_ref: String,
    pub content: Value,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReasonSpace {
    Physical,
    Abstract,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Placement3D {
    pub target: RCPReference,
    pub position: [f64; 3],
    pub direction: Option<[f64; 3]>,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReasonUnitObject {
    pub id: String,
    pub space: ReasonSpace,
    pub coordinate_frame: String,
    pub coordinate_unit: String,
    pub unit_refs: Vec<String>,
    pub structure_refs: Vec<String>,
    pub relation_refs: Vec<String>,
    pub placements: Vec<Placement3D>,
}
// Execution records refer to structural units but never act as structural origins.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionState {
    pub id: String,
    pub revision: u64,
    pub changed_fields: Vec<String>,
    pub goal_status: String,
    pub semantic_subject: Value,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionBinding {
    pub id: String,
    pub reason_unit_ref: String,
    pub execution_state_ref: String,
    pub evidence_refs: Vec<String>,
    pub execution_relation_refs: Vec<String>,
    pub status: String,
    pub lifecycle: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionRelation {
    pub id: String,
    pub kind: String,
    pub source_ref: String,
    pub target_ref: String,
}
fn body<T: serde::de::DeserializeOwned>(record: &RCPRecord) -> Result<T> {
    serde_json::from_value(record.value.clone()).map_err(|e| format!("RCP-STRUCT-001: {e}"))
}
fn member<'a>(
    records: &BTreeMap<&str, &'a RCPRecord>,
    owner: &RCPRecord,
    identity: &str,
    kind: ReferenceKind,
) -> Result<&'a RCPRecord> {
    let reference = RCPReference {
        kind,
        id: identity.into(),
    };
    if !owner.references.contains(&reference) {
        return error("structural reference missing from manifest");
    }
    records
        .get(identity)
        .copied()
        .filter(|r| r.reference == reference)
        .ok_or_else(|| "RCP-STRUCT-001: structural reference missing or mistyped".into())
}
fn distinct(ids: &[String]) -> Result<()> {
    let mut seen = BTreeSet::new();
    for value in ids {
        id(value)?;
        if !seen.insert(value) {
            return error("duplicate structural member");
        }
    }
    Ok(())
}
fn relations(
    records: &BTreeMap<&str, &RCPRecord>,
    owner: &RCPRecord,
    ids: &[String],
    members: &BTreeSet<&str>,
    domain: RelationDomain,
) -> Result<()> {
    distinct(ids)?;
    for identity in ids {
        let relation: ReasonRelation =
            body(member(records, owner, identity, ReferenceKind::Relation)?)?;
        if relation.domain != domain
            || !members.contains(relation.source_ref.as_str())
            || !members.contains(relation.target_ref.as_str())
        {
            return error("relation domain or structural endpoint mismatch");
        }
    }
    Ok(())
}
/// Validate typed structures against the existing payload reference registry.
pub(crate) fn validate_record(
    records: &BTreeMap<&str, &RCPRecord>,
    record: &RCPRecord,
) -> Result<()> {
    match record.reference.kind {
        ReferenceKind::RU => {
            let unit: ReasonUnit = body(record)?;
            if unit.kind.trim().is_empty() {
                return error("RU kind is empty");
            }
        }
        ReferenceKind::RUS => {
            let structure: ReasonUnitStructure = body(record)?;
            if structure.unit_refs.len() < 2 {
                return error("RUS requires multiple RU members");
            }
            distinct(&structure.unit_refs)?;
            for identity in &structure.unit_refs {
                member(records, record, identity, ReferenceKind::RU)?;
            }
            let members = structure.unit_refs.iter().map(String::as_str).collect();
            relations(
                records,
                record,
                &structure.relation_refs,
                &members,
                RelationDomain::NonSpatial,
            )?;
        }
        ReferenceKind::RUO => {
            let object: ReasonUnitObject = body(record)?;
            if object.unit_refs.is_empty()
                || object.coordinate_frame.trim().is_empty()
                || object.coordinate_unit.trim().is_empty()
            {
                return error("RUO needs members, frame and coordinate unit");
            }
            distinct(&object.unit_refs)?;
            distinct(&object.structure_refs)?;
            let mut members = BTreeSet::new();
            for identity in &object.unit_refs {
                member(records, record, identity, ReferenceKind::RU)?;
                members.insert(identity.as_str());
            }
            for identity in &object.structure_refs {
                let structure: ReasonUnitStructure =
                    body(member(records, record, identity, ReferenceKind::RUS)?)?;
                if structure
                    .unit_refs
                    .iter()
                    .any(|id| !object.unit_refs.contains(id))
                {
                    return error("contained RUS has unplaced RU members");
                }
                members.insert(identity.as_str());
            }
            let mut placed = BTreeSet::new();
            for placement in &object.placements {
                if !matches!(
                    placement.target.kind,
                    ReferenceKind::RU | ReferenceKind::RUS
                ) || !members.contains(placement.target.id.as_str())
                    || !placed.insert(placement.target.id.as_str())
                {
                    return error("invalid or duplicate 3D placement");
                }
                member(
                    records,
                    record,
                    &placement.target.id,
                    placement.target.kind.clone(),
                )?;
                if placement.position.iter().any(|v| !v.is_finite())
                    || placement.direction.is_some_and(|v| {
                        v.iter().any(|x| !x.is_finite()) || v.iter().all(|x| *x == 0.0)
                    })
                {
                    return error("invalid 3D position or direction");
                }
            }
            if placed != members {
                return error("explicit 3D placement required for each member");
            }
            relations(
                records,
                record,
                &object.relation_refs,
                &members,
                RelationDomain::Spatial3D,
            )?;
        }
        ReferenceKind::Relation => {
            let relation: ReasonRelation = body(record)?;
            let kinds: &[&str] = match relation.domain {
                RelationDomain::NonSpatial => &[
                    "Dependency",
                    "Cause",
                    "Logical",
                    "Hierarchy",
                    "IsA",
                    "PartOf",
                    "Constraint",
                    "Similar",
                ],
                RelationDomain::Spatial3D => &[
                    "Position",
                    "Direction",
                    "Distance",
                    "Adjacent",
                    "Contains",
                    "Spatial",
                ],
            };
            if !kinds.contains(&relation.kind.as_str()) {
                return error("relation kind does not belong to its domain");
            }
            for identity in [&relation.source_ref, &relation.target_ref] {
                let target = records
                    .get(identity.as_str())
                    .ok_or("RCP-STRUCT-001: relation endpoint missing")?;
                if !matches!(
                    target.reference.kind,
                    ReferenceKind::RU | ReferenceKind::RUS
                ) {
                    return error("relation endpoint must be RU or RUS");
                }
                member(records, record, identity, target.reference.kind.clone())?;
            }
        }
        ReferenceKind::ExecutionState => {
            let state: ExecutionState = body(record)?;
            if !["ACTIVE", "REACHED"].contains(&state.goal_status.as_str()) {
                return error("invalid execution goal status");
            }
        }
        ReferenceKind::ExecutionBinding => {
            let binding: ExecutionBinding = body(record)?;
            if !["CREATED", "ACTIVE", "VERIFIED", "REJECTED", "COMPLETED"]
                .contains(&binding.status.as_str())
                || binding
                    .lifecycle
                    .iter()
                    .any(|state| !["CREATED", "ACTIVE", "COMPLETED"].contains(&state.as_str()))
            {
                return error("invalid execution lifecycle");
            }
            member(records, record, &binding.reason_unit_ref, ReferenceKind::RU)?;
            member(
                records,
                record,
                &binding.execution_state_ref,
                ReferenceKind::ExecutionState,
            )?;
            for identity in &binding.evidence_refs {
                member(records, record, identity, ReferenceKind::Evidence)?;
            }
            for identity in &binding.execution_relation_refs {
                member(records, record, identity, ReferenceKind::ExecutionRelation)?;
            }
        }
        ReferenceKind::ExecutionRelation => {
            let relation: ExecutionRelation = body(record)?;
            if relation.kind.trim().is_empty() {
                return error("empty execution relation kind");
            }
            member(records, record, &relation.source_ref, ReferenceKind::RU)?;
            member(
                records,
                record,
                &relation.target_ref,
                ReferenceKind::Evidence,
            )?;
        }
        _ => {}
    }
    Ok(())
}
