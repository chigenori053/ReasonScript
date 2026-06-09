use reasonscript_runtime::core::types::{UnitType, StateType, RelationType, TransitionType};
use reasonscript_runtime::core::{ReasonUnit, State, Transition, transition::TransitionOp, TypeChecker};
use reasonscript_runtime::graph::{ReasonGraph, Node, Edge};
use ndarray::array;

#[test]
fn test_type_checker_valid_transition() {
    let mut graph = ReasonGraph::default();
    
    // Concept --IsA--> Concept
    let state_a = State::new(StateType::Concept, ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]));
    let state_b = State::new(StateType::Concept, ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0]));
    
    let id_sa = graph.add_state(state_a);
    let id_sb = graph.add_state(state_b);
    let id_na = graph.add_node(Node::new(id_sa));
    let id_nb = graph.add_node(Node::new(id_sb));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));
    graph.add_edge(Edge::new(id_na, id_nb, RelationType::IsA, t));
    
    assert!(TypeChecker::check_graph(&graph).is_ok(), "Concept -> IsA -> Concept should be valid");
}

#[test]
fn test_type_checker_invalid_transition() {
    let mut graph = ReasonGraph::default();
    
    // Action --IsA--> Object (Invalid)
    let state_a = State::new(StateType::Action, ReasonUnit::new("Run", UnitType::Symbolic, array![1.0]));
    let state_b = State::new(StateType::Object, ReasonUnit::new("Car", UnitType::Symbolic, array![1.0]));
    
    let id_sa = graph.add_state(state_a);
    let id_sb = graph.add_state(state_b);
    let id_na = graph.add_node(Node::new(id_sa));
    let id_nb = graph.add_node(Node::new(id_sb));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));
    graph.add_edge(Edge::new(id_na, id_nb, RelationType::IsA, t));
    
    let result = TypeChecker::check_graph(&graph);
    assert!(result.is_err(), "Action -> IsA -> Object should be invalid");
    if let Err(e) = result {
        assert!(e.message.contains("Invalid relation"));
    }
}
