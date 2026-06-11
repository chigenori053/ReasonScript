use uuid::Uuid;
use serde::{Deserialize, Serialize};
use crate::core::DynamicsContext;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TraceEvent {
    Activation(Uuid),
    Propagation { source: Uuid, target: Uuid, edge_id: Uuid },
    Closure { source: Uuid, target: Uuid, relation_id: Uuid },
    IdentityFormation { fragments: Vec<Uuid>, identity_id: Uuid },
    IdentityStabilization(Uuid),
    IdentityTransition { from: Uuid, to: Uuid },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionContext {
    pub active_nodes: Vec<Uuid>,
    pub history: Vec<Uuid>, // Edge IDs representing transitions
    pub timestamp: u64,
    pub dynamics: DynamicsContext,
    pub trace: Vec<TraceEvent>,
}

impl ExecutionContext {
    pub fn new() -> Self {
        Self {
            active_nodes: Vec::new(),
            history: Vec::new(),
            timestamp: 0,
            dynamics: DynamicsContext::new(10), // Default max depth 10
            trace: Vec::new(),
        }
    }

    pub fn record_trace(&mut self, event: TraceEvent) {
        self.trace.push(event);
    }
}
