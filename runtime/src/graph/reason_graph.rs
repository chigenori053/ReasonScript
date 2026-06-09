use crate::graph::{Node, Edge};
use crate::core::State;
use serde::{Deserialize, Serialize};
use indexmap::IndexMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ReasonGraph {
    pub nodes: IndexMap<Uuid, Node>,
    pub edges: Vec<Edge>,
    pub states: IndexMap<Uuid, State>,
}

impl ReasonGraph {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_node(&mut self, node: Node) -> Uuid {
        let id = node.id;
        self.nodes.insert(id, node);
        id
    }

    pub fn add_edge(&mut self, edge: Edge) {
        self.edges.push(edge);
    }

    pub fn add_state(&mut self, state: State) -> Uuid {
        let id = state.id;
        self.states.insert(id, state);
        id
    }

    pub fn get_node_state(&self, node_id: &Uuid) -> Option<&State> {
        self.nodes.get(node_id).and_then(|n| self.states.get(&n.state_id))
    }
}
