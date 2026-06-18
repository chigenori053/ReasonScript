use ndarray::array;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{transition::TransitionOp, ReasonUnit, State, Transition};
use reasonscript_runtime_real::core::{
    SemanticConstraint, SemanticContext, SemanticError, SemanticRule, SemanticValidator,
};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};

#[test]
fn test_semantic_constraint_valid() {
    let mut graph = ReasonGraph::default();
    let context = SemanticContext::new(0.7);

    // Rain --Cause--> Flood
    let state_a = State::new(
        StateType::Event,
        ReasonUnit::new("Rain", UnitType::Symbolic, array![1.0]),
    );
    let state_b = State::new(
        StateType::Event,
        ReasonUnit::new("Flood", UnitType::Symbolic, array![1.0]),
    );

    let id_sa = graph.add_state(state_a);
    let id_sb = graph.add_state(state_b);
    let id_na = graph.add_node(Node::new(id_sa));
    let id_nb = graph.add_node(Node::new(id_sb));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    let mut edge = Edge::new(id_na, id_nb, RelationType::Cause, t);
    edge.cost = 0.9; // Confidence
    graph.add_edge(edge);

    assert!(SemanticValidator::validate_graph(&graph, &context).is_ok());
}

#[test]
fn test_semantic_constraint_rejected_fact() {
    let mut graph = ReasonGraph::default();
    let mut context = SemanticContext::new(0.7);

    let state_a = State::new(
        StateType::Event,
        ReasonUnit::new("Flood", UnitType::Symbolic, array![1.0]),
    );
    let state_b = State::new(
        StateType::Event,
        ReasonUnit::new("Rain", UnitType::Symbolic, array![1.0]),
    );

    let id_sa = graph.add_state(state_a);
    let id_sb = graph.add_state(state_b);
    let id_na = graph.add_node(Node::new(id_sa));
    let id_nb = graph.add_node(Node::new(id_sb));

    // Register Flood -> Cause -> Rain as rejected fact
    context.add_rejected_fact(SemanticConstraint::new(
        SemanticRule::CausalConsistency,
        id_sa,
        id_sb,
        RelationType::Cause,
        1.0,
    ));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_na, id_nb, RelationType::Cause, t));

    let result = SemanticValidator::validate_graph(&graph, &context);
    assert!(
        result.is_err(),
        "Flood -> Cause -> Rain should be semantically invalid"
    );
    if let Err(SemanticError::InvalidCausalRelation(_)) = result {
        // Expected
    } else {
        panic!("Expected InvalidCausalRelation error");
    }
}
