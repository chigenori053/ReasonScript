use reasonscript_runtime_real::core::{ReasonUnit, State, Transition, SemanticContext};
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{UnitType, StateType, RelationType, TransitionType};
use reasonscript_runtime_real::graph::{ReasonGraph, Node, Edge};
use reasonscript_runtime_real::executor::{Executor, ExecutionContext};
use ndarray::{Array1, array};

#[test]
fn sf_a_001_reasonunit_baseline() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));

    // Dog IsA Mammal IsA Animal (All Concepts)
    let id_dog_s = graph.add_state(State::new(StateType::Concept, ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0])));
    let id_dog = graph.add_node(Node::new(id_dog_s));
    let id_mammal_s = graph.add_state(State::new(StateType::Concept, ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0])));
    let id_mammal = graph.add_node(Node::new(id_mammal_s));
    let id_animal_s = graph.add_state(State::new(StateType::Concept, ReasonUnit::new("Animal", UnitType::Symbolic, array![1.0])));
    let id_animal = graph.add_node(Node::new(id_animal_s));

    graph.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(id_mammal, id_animal, RelationType::IsA, t.clone()));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_dog).unwrap();

    let dog_is_animal = graph.edges.iter().any(|e| e.source == id_dog && e.target == id_animal && e.relation == RelationType::IsA);
    assert!(dog_is_animal, "SF-A-001: RU Baseline inference failed");
}

#[test]
fn sf_a_002_fragment_decomposition_and_type_failure() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));

    // Fragments as Attributes (not Concepts)
    let id_animal_s = graph.add_state(State::new(StateType::Attribute, ReasonUnit::new("Animal_F", UnitType::Symbolic, array![1.0])));
    let id_animal = graph.add_node(Node::new(id_animal_s));
    let id_canine_s = graph.add_state(State::new(StateType::Attribute, ReasonUnit::new("Canine_F", UnitType::Symbolic, array![1.0])));
    let id_canine = graph.add_node(Node::new(id_canine_s));
    let id_domestic_s = graph.add_state(State::new(StateType::Attribute, ReasonUnit::new("Domestic_F", UnitType::Symbolic, array![1.0])));
    let id_domestic = graph.add_node(Node::new(id_domestic_s));

    // Try to add IsA between Attributes
    graph.add_edge(Edge::new(id_canine, id_animal, RelationType::IsA, t.clone()));

    // This should fail TypeChecker during infer()
    let result = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_canine);
    
    assert!(result.is_err(), "SF-A-002: Inference should fail for Attribute fragments");
    println!("SF-A-002 Result: {:?}", result.err().unwrap());
}

#[test]
fn sf_b_001_fragment_inference_isolation() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));

    // Even if we skip TypeChecker, fragments lack the Identity (ReasonUnit) to form a meaningful concept chain
    // In v0.1, we represent this by showing that individual fragments don't trigger the same closure 
    // if they are not part of a Concept.
    
    let id_canine_s = graph.add_state(State::new(StateType::Attribute, ReasonUnit::new("Canine", UnitType::Symbolic, array![1.0])));
    let id_canine = graph.add_node(Node::new(id_canine_s));
    let id_mammal_s = graph.add_state(State::new(StateType::Attribute, ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0])));
    let id_mammal = graph.add_node(Node::new(id_mammal_s));
    let id_animal_s = graph.add_state(State::new(StateType::Attribute, ReasonUnit::new("Animal", UnitType::Symbolic, array![1.0])));
    let id_animal = graph.add_node(Node::new(id_animal_s));

    // Using Similar (which doesn't close) to represent fragment relationships
    graph.add_edge(Edge::new(id_canine, id_mammal, RelationType::Similar, t.clone()));
    graph.add_edge(Edge::new(id_mammal, id_animal, RelationType::Similar, t.clone()));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_canine).unwrap();

    let canine_is_animal = graph.edges.iter().any(|e| e.source == id_canine && e.target == id_animal);
    assert!(!canine_is_animal, "SF-B-001: Fragments should not form inference closure");
}

#[test]
fn sf_c_001_dog_reconstruction() {
    // SF vectors
    let animal_f = ReasonUnit::new("Animal", UnitType::Real, Array1::from_vec(vec![1.0, 0.0, 0.0]));
    let canine_f = ReasonUnit::new("Canine", UnitType::Real, Array1::from_vec(vec![0.0, 1.0, 0.0]));
    let domestic_f = ReasonUnit::new("Domestic", UnitType::Real, Array1::from_vec(vec![0.0, 0.0, 1.0]));

    // Reconstruction via composition (addition)
    let reconstructed_dog = animal_f.add(&canine_f).add(&domestic_f);
    
    let expected_dog_vec = array![1.0, 1.0, 1.0];
    
    println!("Reconstructed Dog: {:?}", reconstructed_dog.label);
    println!("Vector: {:?}", reconstructed_dog.vector);
    
    assert_eq!(reconstructed_dog.vector, expected_dog_vec, "SF-C-001: Reconstruction vector mismatch");
    assert!(reconstructed_dog.label.contains("Dog") || reconstructed_dog.label.contains("Animal"), "Label should reflect components");
}

#[test]
fn sf_d_001_trace_comparison() {
    let mut graph_ru = ReasonGraph::default();
    let mut graph_sf = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));

    // RU Case
    let id_dog_s = graph_ru.add_state(State::new(StateType::Concept, ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0])));
    let id_dog = graph_ru.add_node(Node::new(id_dog_s));
    let id_mammal_s = graph_ru.add_state(State::new(StateType::Concept, ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0])));
    let id_mammal = graph_ru.add_node(Node::new(id_mammal_s));
    graph_ru.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t.clone()));

    let mut ctx_ru = ExecutionContext::new();
    Executor::infer(&mut graph_ru, &mut ctx_ru, &semantic_context, id_dog).unwrap();

    // SF Case (Attributes, no closure)
    let id_c_s = graph_sf.add_state(State::new(StateType::Attribute, ReasonUnit::new("Canine", UnitType::Symbolic, array![1.0])));
    let id_c = graph_sf.add_node(Node::new(id_c_s));
    let id_m_s = graph_sf.add_state(State::new(StateType::Attribute, ReasonUnit::new("Mammal_F", UnitType::Symbolic, array![1.0])));
    let id_m = graph_sf.add_node(Node::new(id_m_s));
    graph_sf.add_edge(Edge::new(id_c, id_m, RelationType::Similar, t.clone()));

    let mut ctx_sf = ExecutionContext::new();
    Executor::infer(&mut graph_sf, &mut ctx_sf, &semantic_context, id_c).unwrap();

    println!("RU Trace Length: {}", ctx_ru.trace.len());
    println!("SF Trace Length: {}", ctx_sf.trace.len());

    // RU inference involves Activation + Propagation (+ Closure if chained)
    // SF (Similar) involves Activation + Propagation but NO Closure
    assert!(ctx_ru.trace.len() >= ctx_sf.trace.len());
}
