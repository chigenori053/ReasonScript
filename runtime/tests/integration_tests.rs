use reasonscript_runtime::core::types::{UnitType, StateType, RelationType, TransitionType};
use reasonscript_runtime::core::{ReasonUnit, State, Transition, transition::TransitionOp};
use reasonscript_runtime::core::{SemanticContext, SemanticRule, SemanticConstraint};
use reasonscript_runtime::graph::{ReasonGraph, Node, Edge};
use reasonscript_runtime::executor::{Executor, ExecutionContext};
use ndarray::array;

#[test]
fn test_full_runtime_integration() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    
    // Graph: Dog --IsA--> Mammal
    let state_dog = State::new(StateType::Concept, ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]));
    let state_mammal = State::new(StateType::Concept, ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0]));
    
    let id_state_dog = graph.add_state(state_dog);
    let id_state_mammal = graph.add_state(state_mammal);
    let id_node_dog = graph.add_node(Node::new(id_state_dog));
    let id_node_mammal = graph.add_node(Node::new(id_state_mammal));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));
    let edge = Edge::new(id_node_dog, id_node_mammal, RelationType::IsA, t);
    graph.add_edge(edge);
    
    // Execute Infer(Dog)
    // Expect: TypeCheck OK -> SemanticCheck OK -> Context Updated
    let result = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_node_dog);
    
    assert!(result.is_ok(), "Inference step should succeed for a well-typed, semantically valid graph");
    assert!(result.unwrap());
    assert!(exec_context.timestamp >= 1);
    assert!(exec_context.active_nodes.contains(&id_node_mammal), "Target node should be activated");
}
