use reasonscript_runtime_real::core::types::{UnitType, StateType, RelationType, TransitionType};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition, transition::TransitionOp};
use reasonscript_runtime_real::graph::{ReasonGraph, Node, Edge};
use reasonscript_runtime_real::ir::{GraphIR, lowering::Lowering, tensor_ir::TensorOp};
use ndarray::array;

#[test]
fn test_tensor_ir_lowering() {
    let mut graph = ReasonGraph::default();
    
    // Create states with 16-dim vectors (as per v0.1 spec defaults)
    let mut vec_a = ndarray::Array1::zeros(16);
    vec_a[0] = 1.0;
    let state_a = State::new(StateType::Concept, ReasonUnit::new("A", UnitType::Vector, vec_a.clone()));
    
    let mut vec_b = ndarray::Array1::zeros(16);
    vec_b[1] = 2.0;
    let state_b = State::new(StateType::Concept, ReasonUnit::new("B", UnitType::Vector, vec_b.clone()));
    
    let id_sa = graph.add_state(state_a);
    let id_sb = graph.add_state(state_b);
    let id_na = graph.add_node(Node::new(id_sa));
    let id_nb = graph.add_node(Node::new(id_sb));
    
    let trans_op = TransitionOp::Addition(ReasonUnit::new("Add", UnitType::Vector, vec_b.clone()));
    let transition = Transition::new(TransitionType::Deduction, trans_op);
    graph.add_edge(Edge::new(id_na, id_nb, RelationType::IsA, transition));
    
    let graph_ir = GraphIR { graph };
    let tensor_ir = Lowering::lower(&graph_ir);
    
    // Check state matrix shape (2 nodes, 16 dimensions)
    assert_eq!(tensor_ir.state_matrix.shape(), &[2, 16]);
    
    // Check that vector values are correctly mapped to state matrix
    assert_eq!(tensor_ir.state_matrix[[0, 0]], 1.0); // Node A
    assert_eq!(tensor_ir.state_matrix[[1, 1]], 2.0); // Node B
    
    // Check transition ops
    assert_eq!(tensor_ir.transition_ops.len(), 1);
    if let TensorOp::Add(mat) = &tensor_ir.transition_ops[0] {
        assert_eq!(mat.shape(), &[2, 16]);
        assert_eq!(mat[[0, 1]], 2.0); // The addition vector is applied
    } else {
        panic!("Expected TensorOp::Add");
    }
}
