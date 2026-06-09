use reasonscript_runtime::core::types::{UnitType, StateType, RelationType, TransitionType};
use reasonscript_runtime::core::{ReasonUnit, State, Transition, transition::TransitionOp, SemanticContext};
use reasonscript_runtime::graph::{ReasonGraph, Node, Edge};
use reasonscript_runtime::executor::{Executor, ExecutionContext};
use ndarray::array;

#[test]
fn test_executor_infer_valid() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    
    // Dog --IsA--> Mammal
    let state_a = State::new(StateType::Concept, ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]));
    let state_b = State::new(StateType::Concept, ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0]));
    
    let id_sa = graph.add_state(state_a);
    let id_sb = graph.add_state(state_b);
    let id_na = graph.add_node(Node::new(id_sa));
    let id_nb = graph.add_node(Node::new(id_sb));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));
    let edge = Edge::new(id_na, id_nb, RelationType::IsA, t);
    let edge_id = edge.id;
    graph.add_edge(edge);
    
    let result = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_na);
    
    assert!(result.is_ok());
    assert!(result.unwrap(), "Inference should succeed");
    
    // Check ExecutionContext updates
    assert!(exec_context.active_nodes.contains(&id_na));
    assert!(exec_context.active_nodes.contains(&id_nb));
    assert!(exec_context.history.contains(&edge_id));
    assert_eq!(exec_context.timestamp, 1);
}

#[test]
fn test_executor_infer_invalid_type() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    
    // Action --IsA--> Object (Invalid)
    let state_a = State::new(StateType::Action, ReasonUnit::new("Run", UnitType::Symbolic, array![1.0]));
    let state_b = State::new(StateType::Object, ReasonUnit::new("Car", UnitType::Symbolic, array![1.0]));
    
    let id_sa = graph.add_state(state_a);
    let id_sb = graph.add_state(state_b);
    let id_na = graph.add_node(Node::new(id_sa));
    let id_nb = graph.add_node(Node::new(id_sb));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));
    graph.add_edge(Edge::new(id_na, id_nb, RelationType::IsA, t));
    
    let result = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_na);
    
    assert!(result.is_err());
    // Context should not be updated on error
    assert_eq!(exec_context.timestamp, 0);
}
