use crate::core::{ReasonUnit, Type};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Node {
    pub id: Uuid,
    pub unit: ReasonUnit,
    pub kind: Type,
}

impl Node {
    pub fn new(unit: ReasonUnit, kind: Type) -> Self {
        Self {
            id: Uuid::new_v4(),
            unit,
            kind,
        }
    }
}
