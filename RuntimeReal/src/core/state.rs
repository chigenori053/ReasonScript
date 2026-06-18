use crate::core::types::StateType;
use crate::core::ReasonUnit;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct State {
    pub id: Uuid,
    pub state_type: StateType,
    pub value: ReasonUnit,
}

impl State {
    pub fn new(state_type: StateType, value: ReasonUnit) -> Self {
        Self {
            id: Uuid::new_v4(),
            state_type,
            value,
        }
    }
}
