use crate::ir::{GraphIR, TensorIR, tensor_ir::TensorOp};
use ndarray::Array2;

pub struct Lowering;

impl Lowering {
    pub fn lower(graph_ir: &GraphIR) -> TensorIR {
        // Simple lowering: extract vectors from nodes as state matrix
        let dim = 16; // Standard dim for v0.1
        let n_nodes = graph_ir.graph.nodes.len();
        let mut state_matrix = Array2::zeros((n_nodes, dim));
        
        for (i, node) in graph_ir.graph.nodes.values().enumerate() {
            if let Some(state) = graph_ir.graph.states.get(&node.state_id) {
                for j in 0..dim {
                    state_matrix[[i, j]] = state.value.vector[j];
                }
            }
        }

        let mut transition_ops = Vec::new();
        for edge in &graph_ir.graph.edges {
            match &edge.transition {
                crate::core::Transition::Addition(unit) => {
                    let mut mat = Array2::zeros((n_nodes, dim));
                    // Simple broadcast addition for now
                    for i in 0..n_nodes {
                        for j in 0..dim {
                            mat[[i, j]] = unit.vector[j];
                        }
                    }
                    transition_ops.push(TensorOp::Add(mat));
                }
                crate::core::Transition::Refinement { target, alpha } => {
                    let mut mat = Array2::zeros((n_nodes, dim));
                    for i in 0..n_nodes {
                        for j in 0..dim {
                            mat[[i, j]] = target.vector[j];
                        }
                    }
                    transition_ops.push(TensorOp::Lerp { target: mat, alpha: *alpha });
                }
                _ => {}
            }
        }

        TensorIR {
            state_matrix,
            transition_ops,
        }
    }
}
