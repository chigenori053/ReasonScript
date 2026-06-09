use crate::core::Transition;
use crate::core::types::RelationType;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Edge {
    pub id: Uuid,
    pub source: Uuid,
    pub target: Uuid,
    pub relation: RelationType,
    pub transition: Transition,
    pub cost: f64,
}

impl Edge {
    pub fn new(source: Uuid, target: Uuid, relation: RelationType, transition: Transition) -> Self {
        Self {
            id: Uuid::new_v4(),
            source,
            target,
            relation,
            transition,
            cost: 1.0, // Default cost
        }
    }
}
