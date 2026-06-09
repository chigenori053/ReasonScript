use uuid::Uuid;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionContext {
    pub active_nodes: Vec<Uuid>,
    pub history: Vec<Uuid>, // Edge IDs representing transitions
    pub timestamp: u64,
}

impl ExecutionContext {
    pub fn new() -> Self {
        Self {
            active_nodes: Vec::new(),
            history: Vec::new(),
            timestamp: 0,
        }
    }

    pub fn activate(&mut self, node_id: Uuid) {
        if !self.active_nodes.contains(&node_id) {
            self.active_nodes.push(node_id);
        }
    }
}
