use crate::ir::TensorIR;
use crate::graph::ReasonGraph;
use crate::executor::ExecutionContext;
use crate::core::SemanticContext;
use ndarray::Array2;
use uuid::Uuid;

#[derive(Debug)]
pub enum InferenceError {
    TypeError(crate::core::type_system::TypeError),
    SemanticError(crate::core::semantic_validator::SemanticError),
}

impl From<crate::core::type_system::TypeError> for InferenceError {
    fn from(err: crate::core::type_system::TypeError) -> Self {
        InferenceError::TypeError(err)
    }
}

impl From<crate::core::semantic_validator::SemanticError> for InferenceError {
    fn from(err: crate::core::semantic_validator::SemanticError) -> Self {
        InferenceError::SemanticError(err)
    }
}

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
    pub fn infer(
        graph: &mut ReasonGraph, 
        context: &mut ExecutionContext, 
        semantic_context: &SemanticContext,
        node_id: Uuid
    ) -> Result<bool, InferenceError> {
        
        // 1. Runtime Type Check before execution
        crate::core::type_system::TypeChecker::check_graph(graph)?;

        // 2. Semantic Check
        crate::core::semantic_validator::SemanticValidator::validate_graph(graph, semantic_context)?;

        // 3. Activate
        context.activate(node_id);
        
        // 4. Edge Search (find transitions from active node)
        let reachable_edges: Vec<_> = graph.edges.iter()
            .filter(|e| e.source == node_id)
            .cloned()
            .collect();

        if reachable_edges.is_empty() {
            return Ok(false);
        }

        // 5. Transition
        for edge in reachable_edges {
            // 6. State Update & Graph Update
            context.activate(edge.target);
            context.history.push(edge.id);
            context.timestamp += 1;
        }

        Ok(true)
    }
}
