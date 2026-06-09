use crate::graph::ReasonGraph;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphIR {
    pub graph: ReasonGraph,
}
