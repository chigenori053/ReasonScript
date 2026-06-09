use crate::graph::{Node, Edge};
use serde::{Deserialize, Serialize};
use indexmap::IndexMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ReasonGraph {
    pub nodes: IndexMap<Uuid, Node>,
    pub edges: Vec<Edge>,
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
}
