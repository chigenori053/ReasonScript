use crate::core::Transition;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Edge {
    pub id: Uuid,
    pub source: Uuid,
    pub target: Uuid,
    pub transition: Transition,
}

impl Edge {
    pub fn new(source: Uuid, target: Uuid, transition: Transition) -> Self {
        Self {
            id: Uuid::new_v4(),
            source,
            target,
            transition,
        }
    }
}
