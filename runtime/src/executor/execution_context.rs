use uuid::Uuid;
use serde::{Deserialize, Serialize};
use crate::core::DynamicsContext;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionContext {
    pub active_nodes: Vec<Uuid>,
    pub history: Vec<Uuid>, // Edge IDs representing transitions
    pub timestamp: u64,
    pub dynamics: DynamicsContext,
}

impl ExecutionContext {
    pub fn new() -> Self {
        Self {
            active_nodes: Vec::new(),
            history: Vec::new(),
            timestamp: 0,
            dynamics: DynamicsContext::new(10), // Default max depth 10
        }
    }

    pub fn activate(&mut self, node_id: Uuid) {
        if !self.active_nodes.contains(&node_id) {
            self.active_nodes.push(node_id);
        }
    }
}
