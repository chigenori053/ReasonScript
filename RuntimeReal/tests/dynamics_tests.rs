use ndarray::array;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{transition::TransitionOp, ReasonUnit, State, Transition};
use reasonscript_runtime_real::core::{ActivationState, DynamicsContext, SemanticContext};
use reasonscript_runtime_real::executor::{dynamics::Dynamics, ExecutionContext, Executor};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};

#[test]
fn test_sd_001_activation() {
    let mut graph = ReasonGraph::default();
    let mut context = ExecutionContext::new();
    let s = State::new(
        StateType::Concept,
        ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]),
    );
    let id_s = graph.add_state(s);
    let id = graph.add_node(Node::new(id_s));

    Dynamics::activate(&mut context, id);
    assert!(context.dynamics.active_states.contains(&id));
    assert_eq!(context.dynamics.get_state(&id), ActivationState::Active);
}

#[test]
fn test_sd_002_propagation() {
    let mut graph = ReasonGraph::default();
    let mut context = ExecutionContext::new();

    let id_sa = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("A", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_sa));
    let id_sb = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("B", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_sb));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_a, id_b, RelationType::IsA, t));

    Dynamics::activate(&mut context, id_a);
    Dynamics::propagate(&mut graph, &mut context);

    assert_eq!(context.dynamics.get_state(&id_a), ActivationState::Visited);
    assert_eq!(context.dynamics.get_state(&id_b), ActivationState::Active);
}

#[test]
fn test_sd_003_taxonomic_closure() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut context = ExecutionContext::new();

    let id_sa = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_sa));
    let id_sb = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_sb));
    let id_sc = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Animal", UnitType::Symbolic, array![1.0]),
    ));
    let id_c = graph.add_node(Node::new(id_sc));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_a, id_b, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(id_b, id_c, RelationType::IsA, t.clone()));

    let new_edges = Dynamics::closure(&mut graph, &mut context, &semantic_context);
    assert!(new_edges >= 1);

    let closure_exists = graph
        .edges
        .iter()
        .any(|e| e.source == id_a && e.target == id_c && e.relation == RelationType::IsA);
    assert!(closure_exists);
}

#[test]
fn test_sd_004_part_of_closure() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut context = ExecutionContext::new();

    let id_sa = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Cell", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_sa));
    let id_sb = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Organ", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_sb));
    let id_sc = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Body", UnitType::Symbolic, array![1.0]),
    ));
    let id_c = graph.add_node(Node::new(id_sc));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_a, id_b, RelationType::PartOf, t.clone()));
    graph.add_edge(Edge::new(id_b, id_c, RelationType::PartOf, t.clone()));

    let _ = Dynamics::closure(&mut graph, &mut context, &semantic_context);
    let closure_exists = graph
        .edges
        .iter()
        .any(|e| e.source == id_a && e.target == id_c && e.relation == RelationType::PartOf);
    assert!(closure_exists);
}

#[test]
fn test_sd_005_causal_closure() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut context = ExecutionContext::new();

    let id_sa = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("Rain", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_sa));
    let id_sb = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("Flood", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_sb));
    let id_sc = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("Evacuation", UnitType::Symbolic, array![1.0]),
    ));
    let id_c = graph.add_node(Node::new(id_sc));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_a, id_b, RelationType::Cause, t.clone()));
    graph.add_edge(Edge::new(id_b, id_c, RelationType::Cause, t.clone()));

    let _ = Dynamics::closure(&mut graph, &mut context, &semantic_context);
    let closure_exists = graph
        .edges
        .iter()
        .any(|e| e.source == id_a && e.target == id_c && e.relation == RelationType::Cause);
    assert!(closure_exists);
}

#[test]
fn test_sd_006_loop_detection() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();

    let id_sa = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("A", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_sa));
    let id_sb = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("B", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_sb));
    let id_sc = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("C", UnitType::Symbolic, array![1.0]),
    ));
    let id_c = graph.add_node(Node::new(id_sc));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_a, id_b, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(id_b, id_c, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(id_c, id_a, RelationType::IsA, t.clone()));

    let result = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_a);
    assert!(result.is_ok());
}

#[test]
fn test_sd_007_depth_limit() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    exec_context.dynamics.max_depth = 2;

    let id_sa = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("A", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_sa));
    let id_sb = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("B", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_sb));
    let id_sc = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("C", UnitType::Symbolic, array![1.0]),
    ));
    let id_c = graph.add_node(Node::new(id_sc));
    let id_sd = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("D", UnitType::Symbolic, array![1.0]),
    ));
    let id_d = graph.add_node(Node::new(id_sd));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_a, id_b, RelationType::Temporal, t.clone()));
    graph.add_edge(Edge::new(id_b, id_c, RelationType::Temporal, t.clone()));
    graph.add_edge(Edge::new(id_c, id_d, RelationType::Temporal, t.clone()));

    let _ = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_a).unwrap();

    assert_eq!(
        exec_context.dynamics.get_state(&id_d),
        ActivationState::Inactive
    );
    assert_eq!(
        exec_context.dynamics.get_state(&id_c),
        ActivationState::Active
    );
}

#[test]
fn test_sd_008_convergence() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();

    let id_sa = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("A", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_sa));
    let id_sb = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("B", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_sb));

    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );
    graph.add_edge(Edge::new(id_a, id_b, RelationType::IsA, t));

    let _ = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_a).unwrap();

    let initial_timestamp = exec_context.timestamp;
    let _ = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_a).unwrap();

    assert!(exec_context.timestamp >= initial_timestamp);
}
