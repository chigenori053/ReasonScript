use serde::{Deserialize, Serialize};
use uuid::Uuid;
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum ActivationState {
    Inactive,
    Active,
    Visited,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DynamicsContext {
    pub active_states: Vec<Uuid>,
    pub activation_history: Vec<Uuid>,
    pub edge_history: Vec<Uuid>,
    pub propagation_depth: usize,
    pub max_depth: usize,
    pub state_map: HashMap<Uuid, ActivationState>,
}

impl DynamicsContext {
    pub fn new(max_depth: usize) -> Self {
        Self {
            active_states: Vec::new(),
            activation_history: Vec::new(),
            edge_history: Vec::new(),
            propagation_depth: 0,
            max_depth,
            state_map: HashMap::new(),
        }
    }

    pub fn get_state(&self, id: &Uuid) -> ActivationState {
        *self.state_map.get(id).unwrap_or(&ActivationState::Inactive)
    }

    pub fn set_state(&mut self, id: Uuid, state: ActivationState) {
        self.state_map.insert(id, state);
    }
}
