use crate::ir::TensorIR;
use crate::graph::ReasonGraph;
use crate::executor::ExecutionContext;
use ndarray::Array2;
use uuid::Uuid;

pub struct Executor;

impl Executor {
    /// Execute Tensor IR (lower level)
    pub fn execute(ir: &TensorIR) -> Array2<f64> {
        let mut current = ir.state_matrix.clone();
        for op in &ir.transition_ops {
            match op {
                crate::ir::tensor_ir::TensorOp::Add(mat) => {
                    current += mat;
                }
                crate::ir::tensor_ir::TensorOp::Mul(mat) => {
                    current = current.dot(mat);
                }
                crate::ir::tensor_ir::TensorOp::Lerp { target, alpha } => {
                    current = &current * (1.0 - alpha) + target * *alpha;
                }
            }
        }
        current
    }

    /// Perform a single inference step on the ReasonGraph (higher level)
    /// Infer(Gt, n) = Gt+1
    pub fn infer(graph: &mut ReasonGraph, context: &mut ExecutionContext, node_id: Uuid) -> bool {
        // 1. Activate
        context.activate(node_id);
        
        // 2. Edge Search (find transitions from active node)
        let reachable_edges: Vec<_> = graph.edges.iter()
            .filter(|e| e.source == node_id)
            .cloned()
            .collect();

        if reachable_edges.is_empty() {
            return false;
        }

        // 3. Transition (Simple deterministic: take first reachable for v0.1)
        for edge in reachable_edges {
            // 4. State Update & Graph Update
            // In v0.1, we simulate state evolution by activating the target node
            context.activate(edge.target);
            context.history.push(edge.id);
            context.timestamp += 1;
            
            // Note: Full StateEvolutionRule S_t -> S_t+1 often involves 
            // the lowering to Tensor IR and execution, but for a single graph step,
            // we track the activated path.
        }

        true
    }
}
