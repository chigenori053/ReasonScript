use reasonscript_runtime_real::core::types::{UnitType, StateType, RelationType, TransitionType};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition, transition::TransitionOp};
use reasonscript_runtime_real::core::{SemanticContext, ActivationState};
use reasonscript_runtime_real::graph::{ReasonGraph, Node, Edge};
use reasonscript_runtime_real::executor::{Executor, ExecutionContext};
use ndarray::{array, Array1};

/// Helper to create a 16D real-valued ReasonUnit
fn create_real_ru(label: &str, values: [f64; 16]) -> ReasonUnit {
    ReasonUnit::new(label, UnitType::Real, Array1::from_vec(values.to_vec()))
}

#[test]
fn test_b_001_real_valued_state_transition() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    
    let ru_dog = create_real_ru("Dog", [1.0; 16]);
    let ru_mammal = create_real_ru("Mammal", [0.9; 16]);
    
    let id_sdog = graph.add_state(State::new(StateType::Concept, ru_dog));
    let id_dog = graph.add_node(Node::new(id_sdog));
    let id_smammal = graph.add_state(State::new(StateType::Concept, ru_mammal));
    let id_mammal = graph.add_node(Node::new(id_smammal));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(16, UnitType::Real)));
    graph.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t));
    
    let result = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_dog);
    
    assert!(result.is_ok());
    assert!(exec_context.dynamics.get_state(&id_mammal) != ActivationState::Inactive);
}

#[test]
fn test_b_002_real_valued_taxonomic_closure() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    
    let ru_dog = create_real_ru("Dog", [1.0; 16]);
    let ru_mammal = create_real_ru("Mammal", [0.9; 16]);
    let ru_animal = create_real_ru("Animal", [0.8; 16]);
    
    let id_sdog = graph.add_state(State::new(StateType::Concept, ru_dog));
    let id_dog = graph.add_node(Node::new(id_sdog));
    let id_smammal = graph.add_state(State::new(StateType::Concept, ru_mammal));
    let id_mammal = graph.add_node(Node::new(id_smammal));
    let id_sanimal = graph.add_state(State::new(StateType::Concept, ru_animal));
    let id_animal = graph.add_node(Node::new(id_sanimal));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(16, UnitType::Real)));
    graph.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(id_mammal, id_animal, RelationType::IsA, t.clone()));
    
    let _ = Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_dog).unwrap();
    
    let closure_exists = graph.edges.iter().any(|e| 
        e.source == id_dog && e.target == id_animal && e.relation == RelationType::IsA
    );
    
    assert!(closure_exists, "Real-valued taxonomic closure should generate new edges");
}

#[test]
fn test_b_003_topology_retention() {
    // 1. Symbolic Setup
    let mut g_sym = ReasonGraph::default();
    let mut ex_sym = ExecutionContext::new();
    let sc = SemanticContext::new(0.5);
    
    let id_ss1 = g_sym.add_state(State::new(StateType::Concept, ReasonUnit::new("S1", UnitType::Symbolic, array![1.0])));
    let id_s1 = g_sym.add_node(Node::new(id_ss1));
    let id_ss2 = g_sym.add_state(State::new(StateType::Concept, ReasonUnit::new("S2", UnitType::Symbolic, array![1.0])));
    let id_s2 = g_sym.add_node(Node::new(id_ss2));
    let id_ss3 = g_sym.add_state(State::new(StateType::Concept, ReasonUnit::new("S3", UnitType::Symbolic, array![1.0])));
    let id_s3 = g_sym.add_node(Node::new(id_ss3));
    
    let t_sym = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)));
    g_sym.add_edge(Edge::new(id_s1, id_s2, RelationType::IsA, t_sym.clone()));
    g_sym.add_edge(Edge::new(id_s2, id_s3, RelationType::IsA, t_sym.clone()));
    
    Executor::infer(&mut g_sym, &mut ex_sym, &sc, id_s1).unwrap();
    
    // 2. Real Setup
    let mut g_real = ReasonGraph::default();
    let mut ex_real = ExecutionContext::new();
    
    let id_rs1 = g_real.add_state(State::new(StateType::Concept, create_real_ru("R1", [1.0; 16])));
    let id_r1 = g_real.add_node(Node::new(id_rs1));
    let id_rs2 = g_real.add_state(State::new(StateType::Concept, create_real_ru("R2", [0.9; 16])));
    let id_r2 = g_real.add_node(Node::new(id_rs2));
    let id_rs3 = g_real.add_state(State::new(StateType::Concept, create_real_ru("R3", [0.8; 16])));
    let id_r3 = g_real.add_node(Node::new(id_rs3));
    
    let t_real = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(16, UnitType::Real)));
    g_real.add_edge(Edge::new(id_r1, id_r2, RelationType::IsA, t_real.clone()));
    g_real.add_edge(Edge::new(id_r2, id_r3, RelationType::IsA, t_real.clone()));
    
    Executor::infer(&mut g_real, &mut ex_real, &sc, id_r1).unwrap();
    
    // 3. Comparison
    assert_eq!(ex_sym.active_nodes.len(), ex_real.active_nodes.len());
    assert_eq!(g_sym.edges.len(), g_real.edges.len());
    assert_eq!(ex_sym.timestamp, ex_real.timestamp);
    
    println!("Topology Retention Validation: 100%");
}
