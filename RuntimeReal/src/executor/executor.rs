use crate::core::SemanticContext;
use crate::executor::ExecutionContext;
use crate::graph::ReasonGraph;
use crate::ir::TensorIR;
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
        node_id: Uuid,
    ) -> Result<bool, InferenceError> {
        // 1. Semantic structure and context checks before execution
        crate::core::semantic_validator::SemanticValidator::validate_graph(
            graph,
            semantic_context,
        )?;

        // 2. Runtime type check
        crate::core::type_system::TypeChecker::check_graph(graph)?;

        // 3. Semantic Dynamics
        // Activate the starting node
        crate::executor::dynamics::Dynamics::activate(context, node_id);

        // Run dynamics cycle until convergence or limit reached
        let mut converged = false;
        let mut iterations = 0;
        let max_iterations = 100; // Safety limit

        while !converged && iterations < max_iterations {
            converged =
                crate::executor::dynamics::Dynamics::run_cycle(graph, context, semantic_context);
            context.timestamp += 1;
            iterations += 1;
        }

        // Sync legacy fields for backward compatibility
        context.active_nodes = context.dynamics.activation_history.clone();
        context.history = context.dynamics.edge_history.clone();

        Ok(true)
    }
}
