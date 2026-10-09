//! UNKNOWN structural forms share UnknownRegistry; no resolver or spatial inference.
use crate::rcp::{
    RCPRecord, RCPReference, RCPResult, ReferenceKind, UnknownRegistry, UnknownState, UnknownUnit,
};
use crate::structure::{ReasonSpace, ReasonUnitObject};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

pub const PROFILE: &str = "reasonscript-unknown-structure/0.1";
pub type UnknownReasonUnit = UnknownUnit;

// Nullable spatial values are still required: absence must not masquerade as unknown.
fn nullable<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(deserializer)
}

/// Optional description of the same URU identity, without a second state journal.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownInformation {
    pub id: String,
    pub known_information: Value,
    pub missing_information: Value,
    pub evidence_refs: Vec<String>,
    pub knowledge_refs: Vec<String>,
    pub causal_refs: Vec<RCPReference>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum UnknownRelationKind {
    DependsOn,
    CausedBy,
    Blocks,
    RelatedTo,
    ConflictsWith,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownRelation {
    pub id: String,
    pub kind: UnknownRelationKind,
    pub source: RCPReference,
    pub target: RCPReference,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownReasonUnitStructure {
    pub id: String,
    pub uru_refs: Vec<String>,
    pub relation_refs: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PositionStatus {
    Known,
    Unknown,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownPlacement3D {
    pub target: RCPReference,
    pub status: PositionStatus,
    #[serde(deserialize_with = "nullable")]
    pub position: Option<[f64; 3]>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SpatialConstraintKind {
    Adjacent,
    Contains,
    Distance,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownSpatialConstraint {
    pub kind: SpatialConstraintKind,
    pub source: RCPReference,
    pub target: RCPReference,
    #[serde(deserialize_with = "nullable")]
    pub distance: Option<f64>,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnknownReasonUnitObject {
    pub id: String,
    pub space: ReasonSpace,
    pub coordinate_frame: String,
    pub coordinate_unit: String,
    #[serde(deserialize_with = "nullable")]
    pub coordinate_bounds: Option<[[f64; 2]; 3]>,
    pub uru_refs: Vec<String>,
    pub urus_refs: Vec<String>,
    pub ruo_refs: Vec<String>,
    pub placements: Vec<UnknownPlacement3D>,
    pub constraints: Vec<UnknownSpatialConstraint>,
}
fn fail<T>(reason: &str) -> RCPResult<T> {
    Err(format!("URS-001: {reason}"))
}
fn body<T: serde::de::DeserializeOwned>(record: &RCPRecord) -> RCPResult<T> {
    serde_json::from_value(record.value.clone()).map_err(|e| format!("URS-001: {e}"))
}
fn distinct(ids: &[String]) -> RCPResult<()> {
    let mut seen = BTreeSet::new();
    for id in ids {
        crate::StableId::new(id.clone()).map_err(|_| "URS-001: invalid identity")?;
        if !seen.insert(id) {
            return fail("duplicate member");
        }
    }
    Ok(())
}
fn require<'a>(
    records: &BTreeMap<&str, &'a RCPRecord>,
    units: &BTreeMap<String, &UnknownUnit>,
    owner: &RCPRecord,
    reference: &RCPReference,
) -> RCPResult<Option<&'a RCPRecord>> {
    if !owner.references.contains(reference) {
        return fail("reference missing from manifest");
    }
    if reference.kind == ReferenceKind::URU {
        if !units.contains_key(&reference.id) {
            return fail("missing URU");
        }
        return Ok(records.get(reference.id.as_str()).copied());
    }
    records
        .get(reference.id.as_str())
        .copied()
        .filter(|r| r.reference == *reference)
        .map(Some)
        .ok_or_else(|| "URS-001: dangling or mistyped reference".into())
}
fn reference(kind: ReferenceKind, id: &str) -> RCPReference {
    RCPReference {
        kind,
        id: id.into(),
    }
}

impl UnknownReasonUnitStructure {
    /// Stable IDs break ties. This is a structural order, not a resolution decision.
    pub fn reevaluation_order(&self, registry: &UnknownRegistry) -> RCPResult<Vec<String>> {
        self.order(
            &registry
                .units
                .iter()
                .map(|(id, unit)| (id.clone(), unit))
                .collect(),
        )
    }
    fn order(&self, units: &BTreeMap<String, &UnknownUnit>) -> RCPResult<Vec<String>> {
        distinct(&self.uru_refs)?;
        if self.uru_refs.len() < 2 {
            return fail("URUS requires multiple URU");
        }
        let members: BTreeSet<_> = self.uru_refs.iter().cloned().collect();
        let mut pending = BTreeMap::new();
        let mut children: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        let mut ready = BTreeSet::new();
        for id in &members {
            let unit = units.get(id).ok_or("URS-001: unregistered URU")?;
            distinct(&unit.dependencies)?;
            pending.insert(id.clone(), unit.dependencies.len());
            if unit.dependencies.is_empty() {
                ready.insert(id.clone());
            }
            for dependency in &unit.dependencies {
                if !members.contains(dependency) {
                    return fail("URUS must include dependency closure");
                }
                children
                    .entry(dependency.clone())
                    .or_default()
                    .insert(id.clone());
            }
        }
        let mut order = vec![];
        while let Some(id) = ready.pop_first() {
            if let Some(dependents) = children.get(&id) {
                for dependent in dependents {
                    let count = pending.get_mut(dependent).unwrap();
                    *count -= 1;
                    if *count == 0 {
                        ready.insert(dependent.clone());
                    }
                }
            }
            order.push(id);
        }
        if order.len() != members.len() {
            return fail("cyclic URUS dependency");
        }
        Ok(order)
    }
    pub fn unresolved(&self, registry: &UnknownRegistry) -> RCPResult<Vec<String>> {
        Ok(self
            .reevaluation_order(registry)?
            .into_iter()
            .filter(|id| registry.units[id].state() != Some(&UnknownState::Resolved))
            .collect())
    }
    /// All transitive dependents, including resolved units; source code chooses what to reopen.
    pub fn impact(&self, registry: &UnknownRegistry, changed: &str) -> RCPResult<Vec<String>> {
        let order = self.reevaluation_order(registry)?;
        if !self.uru_refs.iter().any(|id| id == changed) {
            return fail("changed URU is not a member");
        }
        let mut affected = BTreeSet::from([changed.to_string()]);
        let mut result = vec![];
        for id in order {
            if id != changed
                && registry.units[&id]
                    .dependencies
                    .iter()
                    .any(|dependency| affected.contains(dependency))
            {
                affected.insert(id.clone());
                result.push(id);
            }
        }
        Ok(result)
    }
    pub fn resolved_impact(
        &self,
        registry: &UnknownRegistry,
        changed: &str,
    ) -> RCPResult<Vec<String>> {
        Ok(self
            .impact(registry, changed)?
            .into_iter()
            .filter(|id| registry.units[id].state() == Some(&UnknownState::Resolved))
            .collect())
    }
}

pub(crate) fn validate_record(
    records: &BTreeMap<&str, &RCPRecord>,
    units: &BTreeMap<String, &UnknownUnit>,
    record: &RCPRecord,
) -> RCPResult<()> {
    match record.reference.kind {
        ReferenceKind::URU => {
            let information: UnknownInformation = body(record)?;
            if !units.contains_key(&information.id) {
                return fail("URU description has no UNKNOWN body");
            }
            for (ids, kind) in [
                (&information.evidence_refs, ReferenceKind::Evidence),
                (&information.knowledge_refs, ReferenceKind::Knowledge),
            ] {
                distinct(ids)?;
                for id in ids {
                    require(records, units, record, &reference(kind.clone(), id))?;
                }
            }
            for causal in &information.causal_refs {
                if !matches!(
                    causal.kind,
                    ReferenceKind::Relation | ReferenceKind::UnknownRelation
                ) {
                    return fail("invalid causal reference kind");
                }
                require(records, units, record, causal)?;
            }
        }
        ReferenceKind::UnknownRelation => {
            let relation: UnknownRelation = body(record)?;
            if relation.source.kind != ReferenceKind::URU {
                return fail("relation source must be URU");
            }
            let permitted = relation.target.kind == ReferenceKind::URU
                || (relation.kind == UnknownRelationKind::Blocks
                    && matches!(
                        relation.target.kind,
                        ReferenceKind::RU | ReferenceKind::RUS | ReferenceKind::RUO
                    ));
            if !permitted {
                return fail("invalid unknown relation target");
            }
            require(records, units, record, &relation.source)?;
            require(records, units, record, &relation.target)?;
            if relation.kind == UnknownRelationKind::DependsOn
                && !units[&relation.source.id]
                    .dependencies
                    .contains(&relation.target.id)
            {
                return fail("DEPENDS_ON disagrees with UNKNOWN dependencies");
            }
        }
        ReferenceKind::URUS => {
            let structure: UnknownReasonUnitStructure = body(record)?;
            structure.order(units)?;
            distinct(&structure.relation_refs)?;
            for id in &structure.uru_refs {
                require(records, units, record, &reference(ReferenceKind::URU, id))?;
            }
            for id in &structure.relation_refs {
                let relation: UnknownRelation = body(
                    require(
                        records,
                        units,
                        record,
                        &reference(ReferenceKind::UnknownRelation, id),
                    )?
                    .unwrap(),
                )?;
                if !structure.uru_refs.contains(&relation.source.id)
                    || (relation.target.kind == ReferenceKind::URU
                        && !structure.uru_refs.contains(&relation.target.id))
                {
                    return fail("URUS relation endpoint outside structure");
                }
            }
        }
        ReferenceKind::URUO => {
            let object: UnknownReasonUnitObject = body(record)?;
            if object.uru_refs.is_empty()
                || object.coordinate_frame.trim().is_empty()
                || object.coordinate_unit.trim().is_empty()
            {
                return fail("URUO requires members and coordinate system");
            }
            distinct(&object.uru_refs)?;
            distinct(&object.urus_refs)?;
            distinct(&object.ruo_refs)?;
            if let Some(bounds) = &object.coordinate_bounds {
                if bounds
                    .iter()
                    .any(|pair| pair.iter().any(|n| !n.is_finite()) || pair[0] > pair[1])
                {
                    return fail("invalid coordinate bounds");
                }
            }
            let mut members = BTreeSet::new();
            for id in &object.uru_refs {
                require(records, units, record, &reference(ReferenceKind::URU, id))?;
                members.insert(reference(ReferenceKind::URU, id));
            }
            for id in &object.urus_refs {
                let structure: UnknownReasonUnitStructure = body(
                    require(records, units, record, &reference(ReferenceKind::URUS, id))?.unwrap(),
                )?;
                if structure
                    .uru_refs
                    .iter()
                    .any(|id| !object.uru_refs.contains(id))
                {
                    return fail("contained URUS has unplaced URU");
                }
                members.insert(reference(ReferenceKind::URUS, id));
            }
            for id in &object.ruo_refs {
                let known: ReasonUnitObject = body(
                    require(records, units, record, &reference(ReferenceKind::RUO, id))?.unwrap(),
                )?;
                if known.space != object.space
                    || known.coordinate_frame != object.coordinate_frame
                    || known.coordinate_unit != object.coordinate_unit
                {
                    return fail("linked RUO coordinate system mismatch");
                }
            }
            let mut placed = BTreeSet::new();
            for placement in &object.placements {
                if !members.contains(&placement.target) || !placed.insert(placement.target.clone())
                {
                    return fail("invalid or duplicate unknown placement");
                }
                match (&placement.status, &placement.position) {
                    (PositionStatus::Unknown, None) => {}
                    (PositionStatus::Known, Some(position)) => {
                        if position.iter().any(|n| !n.is_finite())
                            || object.coordinate_bounds.is_some_and(|bounds| {
                                position
                                    .iter()
                                    .zip(bounds)
                                    .any(|(n, pair)| *n < pair[0] || *n > pair[1])
                            })
                        {
                            return fail("known position outside coordinate bounds");
                        }
                    }
                    _ => return fail("position status and coordinates disagree"),
                }
            }
            if placed != members {
                return fail("each member needs explicit known/unknown placement");
            }
            for constraint in &object.constraints {
                if !members.contains(&constraint.source) || !members.contains(&constraint.target) {
                    return fail("constraint endpoint outside spatial members");
                }
                if constraint
                    .distance
                    .is_some_and(|n| !n.is_finite() || n < 0.0)
                    || (constraint.kind != SpatialConstraintKind::Distance
                        && constraint.distance.is_some())
                {
                    return fail("invalid spatial constraint value");
                }
            }
        }
        _ => {}
    }
    Ok(())
}
