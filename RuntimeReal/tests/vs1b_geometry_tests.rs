use reasonscript_runtime_real::core::types::{UnitType, StateType, RelationType, TransitionType};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition, transition::TransitionOp};
use reasonscript_runtime_real::core::SemanticContext;
use reasonscript_runtime_real::graph::{ReasonGraph, Node, Edge};
use reasonscript_runtime_real::executor::{Executor, ExecutionContext};
use ndarray::Array1;
use std::collections::HashMap;

/// Mock Embedding Space for VS-1B
/// Dimensions: 
/// 0: Mammal-ness, 1: Vehicle-ness, 2: Living, 3: Tool, 4: Abstractness
struct MockSpace {
    vectors: HashMap<String, [f64; 16]>,
}

impl MockSpace {
    fn new() -> Self {
        let mut v = HashMap::new();
        // Dog: High Mammal, High Living
        v.insert("Dog".to_string(), [1.0, 0.0, 1.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        // Mammal: Pure Mammal, High Living
        v.insert("Mammal".to_string(), [1.0, 0.0, 1.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        // Animal: High Living, Lower Mammal (General)
        v.insert("Animal".to_string(), [0.5, 0.0, 1.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        // Car: High Vehicle, High Tool, Zero Living
        v.insert("Car".to_string(), [0.0, 1.0, 0.0, 1.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        // Banana: High Living (Plant), Zero Mammal
        v.insert("Banana".to_string(), [0.0, 0.0, 1.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        
        Self { vectors: v }
    }

    fn get_ru(&self, label: &str) -> ReasonUnit {
        let values = self.vectors.get(label).expect("Label not in mock space");
        ReasonUnit::new(label, UnitType::Real, Array1::from_vec(values.to_vec()))
    }
}

fn cosine_similarity(a: &Array1<f64>, b: &Array1<f64>) -> f64 {
    let dot = a.dot(b);
    let norm_a = a.dot(a).sqrt();
    let norm_b = b.dot(b).sqrt();
    if norm_a == 0.0 || norm_b == 0.0 { return 0.0; }
    dot / (norm_a * norm_b)
}

#[test]
fn test_b_004_semantic_distance_preservation() {
    let space = MockSpace::new();
    let ru_dog = space.get_ru("Dog");
    let ru_mammal = space.get_ru("Mammal");
    let ru_car = space.get_ru("Car");
    
    let sim_dm = cosine_similarity(&ru_dog.vector, &ru_mammal.vector);
    let sim_dc = cosine_similarity(&ru_dog.vector, &ru_car.vector);
    
    println!("sim(Dog, Mammal) = {:.4}", sim_dm);
    println!("sim(Dog, Car)    = {:.4}", sim_dc);
    
    assert!(sim_dm > sim_dc, "Dog should be more similar to Mammal than to Car");
}

#[test]
fn test_b_005_semantic_neighborhood() {
    let space = MockSpace::new();
    let ru_dog = space.get_ru("Dog");
    
    let candidates = vec!["Mammal", "Animal", "Car", "Banana"];
    let mut scores: Vec<_> = candidates.iter().map(|&label| {
        let ru = space.get_ru(label);
        (label, cosine_similarity(&ru_dog.vector, &ru.vector))
    }).collect();
    
    // Sort by similarity descending
    scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    
    println!("Neighborhood of Dog: {:?}", scores);
    
    // Top 2 should be Mammal and Animal (or Banana due to 'Living' bit, but Mammal has 2 shared bits)
    assert!(scores[0].0 == "Mammal" || scores[0].0 == "Animal");
    assert!(scores[3].0 == "Car", "Car should be the furthest from Dog");
}

#[test]
fn test_b_006_geometry_closure_correlation() {
    let space = MockSpace::new();
    let mut graph = ReasonGraph::default();
    let sc = SemanticContext::new(0.5);
    let mut ex = ExecutionContext::new();
    
    let id_sdog = graph.add_state(State::new(StateType::Concept, space.get_ru("Dog")));
    let id_dog = graph.add_node(Node::new(id_sdog));
    let id_smammal = graph.add_state(State::new(StateType::Concept, space.get_ru("Mammal")));
    let id_mammal = graph.add_node(Node::new(id_smammal));
    let id_sanimal = graph.add_state(State::new(StateType::Concept, space.get_ru("Animal")));
    let id_animal = graph.add_node(Node::new(id_sanimal));
    
    let t = Transition::new(TransitionType::Deduction, TransitionOp::Addition(ReasonUnit::zero(16, UnitType::Real)));
    graph.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(id_mammal, id_animal, RelationType::IsA, t.clone()));
    
    // Before closure, Dog -> Animal is 2 hops (not an edge). Vector similarity exists.
    let sim_da = cosine_similarity(&space.get_ru("Dog").vector, &space.get_ru("Animal").vector);
    
    Executor::infer(&mut graph, &mut ex, &sc, id_dog).unwrap();
    
    // After closure, Dog -> Animal is 1 hop (direct edge).
    let closure_edge = graph.edges.iter().find(|e| e.source == id_dog && e.target == id_animal).expect("Closure failed");
    
    println!("Sim(Dog, Animal) = {:.4}, Closure Edge Cost = {:.4}", sim_da, closure_edge.cost);
    
    // Correlation: Closure bridges concepts that are already "near" in vector space
    assert!(sim_da > 0.4, "Concepts linked by closure should have significant vector similarity");
}
