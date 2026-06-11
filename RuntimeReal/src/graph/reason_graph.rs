use crate::graph::{Node, Edge};
use crate::core::State;
use crate::core::types::GraphType;
use serde::{Deserialize, Serialize};
use indexmap::IndexMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReasonGraph {
    pub graph_type: GraphType,
    pub nodes: IndexMap<Uuid, Node>,
    pub edges: Vec<Edge>,
    pub states: IndexMap<Uuid, State>,
}

impl Default for ReasonGraph {
    fn default() -> Self {
        Self {
            graph_type: GraphType::ReasonGraph,
            nodes: IndexMap::new(),
            edges: Vec::new(),
            states: IndexMap::new(),
        }
    }
}

impl ReasonGraph {
    pub fn new(graph_type: GraphType) -> Self {
        Self {
            graph_type,
            ..Default::default()
        }
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
