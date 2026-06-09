use crate::core::ReasonUnit;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct State {
    pub id: Uuid,
    pub value: ReasonUnit,
}

impl State {
    pub fn new(value: ReasonUnit) -> Self {
        Self {
            id: Uuid::new_v4(),
            value,
        }
    }
}
