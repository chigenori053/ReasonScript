use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Node {
    pub id: Uuid,
    pub state_id: Uuid,
}

impl Node {
    pub fn new(state_id: Uuid) -> Self {
        Self {
            id: Uuid::new_v4(),
            state_id,
        }
    }
}
