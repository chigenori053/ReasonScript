use serde::{Deserialize, Serialize};
use uuid::Uuid;
use crate::core::types::RelationType;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum SemanticRule {
    TaxonomicConsistency,
    PartWholeConsistency,
    CausalConsistency,
    TemporalConsistency,
    SpatialConsistency,
    ConstraintSatisfaction,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SemanticConstraint {
    pub id: Uuid,
    pub rule: SemanticRule,
    pub source: Uuid, // StateId
    pub target: Uuid, // StateId
    pub relation: RelationType,
    pub confidence: f64, // 0.0 to 1.0
}

impl SemanticConstraint {
    pub fn new(rule: SemanticRule, source: Uuid, target: Uuid, relation: RelationType, confidence: f64) -> Self {
        Self {
            id: Uuid::new_v4(),
            rule,
            source,
            target,
            relation,
            confidence: confidence.clamp(0.0, 1.0),
        }
    }
}
