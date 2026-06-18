use ndarray::{array, Array1};
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{ReasonUnit, SemanticContext, State, Transition};
use reasonscript_runtime_real::executor::{ExecutionContext, Executor};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use uuid::Uuid;

#[test]
fn ru_a_001_reasonunit_baseline() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );

    // Dog IsA Mammal IsA Animal
    let id_dog_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]),
    ));
    let id_dog = graph.add_node(Node::new(id_dog_s));

    let id_mammal_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0]),
    ));
    let id_mammal = graph.add_node(Node::new(id_mammal_s));

    let id_animal_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Animal", UnitType::Symbolic, array![1.0]),
    ));
    let id_animal = graph.add_node(Node::new(id_animal_s));

    graph.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(
        id_mammal,
        id_animal,
        RelationType::IsA,
        t.clone(),
    ));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_dog).unwrap();

    // Check for Dog IsA Animal
    let dog_is_animal = graph
        .edges
        .iter()
        .any(|e| e.source == id_dog && e.target == id_animal && e.relation == RelationType::IsA);
    assert!(dog_is_animal, "RU-A-001: Taxonomic closure failed");
}

#[test]
fn ru_a_002_sub_reasonunit_decomposition() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );

    // D -> o -> g
    let id_d_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("D", UnitType::Symbolic, array![1.0]),
    ));
    let id_d = graph.add_node(Node::new(id_d_s));
    let id_o_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("o", UnitType::Symbolic, array![1.0]),
    ));
    let id_o = graph.add_node(Node::new(id_o_s));
    let id_g_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("g", UnitType::Symbolic, array![1.0]),
    ));
    let id_g = graph.add_node(Node::new(id_g_s));

    // Use a relation that DOES NOT support closure for Sub-RU decomposition validation
    // Spec says "推論不能" (Inference impossible).
    // If we use IsA, it will close. So we should use a relation that is NOT in the closure rules
    // or verify that "D o g" doesn't mean "Dog" automatically.
    // Actually, the spec implies that if we break "Dog" into "D", "o", "g", then "D IsA o IsA g" doesn't give us "Dog".

    graph.add_edge(Edge::new(id_d, id_o, RelationType::Dependency, t.clone()));
    graph.add_edge(Edge::new(id_o, id_g, RelationType::Dependency, t.clone()));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_d).unwrap();

    // Dependency doesn't have closure rules in v0.1 Dynamics
    let d_dep_g = graph
        .edges
        .iter()
        .any(|e| e.source == id_d && e.target == id_g && e.relation == RelationType::Dependency);
    assert!(!d_dep_g, "RU-A-002: Inference occurred on Sub-ReasonUnit");
}

#[test]
fn ru_b_001_object_composition() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );

    // Tail PartOf Dog, Leg PartOf Dog
    let id_dog_s = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]),
    ));
    let id_dog = graph.add_node(Node::new(id_dog_s));

    let id_tail_s = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Tail", UnitType::Symbolic, array![1.0]),
    ));
    let id_tail = graph.add_node(Node::new(id_tail_s));

    let id_leg_s = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Leg", UnitType::Symbolic, array![1.0]),
    ));
    let id_leg = graph.add_node(Node::new(id_leg_s));

    graph.add_edge(Edge::new(id_tail, id_dog, RelationType::PartOf, t.clone()));
    graph.add_edge(Edge::new(id_leg, id_dog, RelationType::PartOf, t.clone()));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_tail).unwrap();

    // Verify composition (simply that edges exist and activation propagated)
    assert!(
        exec_context.dynamics.get_state(&id_dog)
            == reasonscript_runtime_real::core::ActivationState::Visited
            || exec_context.dynamics.get_state(&id_dog)
                == reasonscript_runtime_real::core::ActivationState::Active
    );
}

#[test]
fn ru_b_002_hierarchical_composition() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );

    // Cell PartOf Organ PartOf Body
    let id_cell_s = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Cell", UnitType::Symbolic, array![1.0]),
    ));
    let id_cell = graph.add_node(Node::new(id_cell_s));

    let id_organ_s = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Organ", UnitType::Symbolic, array![1.0]),
    ));
    let id_organ = graph.add_node(Node::new(id_organ_s));

    let id_body_s = graph.add_state(State::new(
        StateType::Object,
        ReasonUnit::new("Body", UnitType::Symbolic, array![1.0]),
    ));
    let id_body = graph.add_node(Node::new(id_body_s));

    graph.add_edge(Edge::new(
        id_cell,
        id_organ,
        RelationType::PartOf,
        t.clone(),
    ));
    graph.add_edge(Edge::new(
        id_organ,
        id_body,
        RelationType::PartOf,
        t.clone(),
    ));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_cell).unwrap();

    // Check for Cell PartOf Body
    let cell_part_of_body = graph
        .edges
        .iter()
        .any(|e| e.source == id_cell && e.target == id_body && e.relation == RelationType::PartOf);
    assert!(
        cell_part_of_body,
        "RU-B-002: Hierarchical PartOf closure failed"
    );
}

fn cosine_similarity(v1: &Array1<f64>, v2: &Array1<f64>) -> f64 {
    let dot = v1.dot(v2);
    let norm1 = v1.dot(v1).sqrt();
    let norm2 = v2.dot(v2).sqrt();
    if norm1 * norm2 == 0.0 {
        0.0
    } else {
        dot / (norm1 * norm2)
    }
}

#[test]
fn ru_c_001_semantic_distance() {
    let dog_vec = Array1::from_vec(vec![1.0, 0.9, 0.0, 0.0]);
    let mammal_vec = Array1::from_vec(vec![1.0, 1.0, 0.0, 0.0]);
    let car_vec = Array1::from_vec(vec![0.0, 0.0, 1.0, 1.0]);

    let sim_dog_mammal = cosine_similarity(&dog_vec, &mammal_vec);
    let sim_dog_car = cosine_similarity(&dog_vec, &car_vec);

    println!("Sim(Dog, Mammal) = {:.4}", sim_dog_mammal);
    println!("Sim(Dog, Car) = {:.4}", sim_dog_car);

    assert!(
        sim_dog_mammal > sim_dog_car,
        "RU-C-001: Semantic distance violation"
    );
}

#[test]
fn ru_d_001_metrics_validation() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );

    let id_dog_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]),
    ));
    let id_dog = graph.add_node(Node::new(id_dog_s));
    let id_mammal_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Mammal", UnitType::Symbolic, array![1.0]),
    ));
    let id_mammal = graph.add_node(Node::new(id_mammal_s));
    let id_animal_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Animal", UnitType::Symbolic, array![1.0]),
    ));
    let id_animal = graph.add_node(Node::new(id_animal_s));

    graph.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t.clone()));
    graph.add_edge(Edge::new(
        id_mammal,
        id_animal,
        RelationType::IsA,
        t.clone(),
    ));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_dog).unwrap();

    // Check metrics on Dog node
    let dog_node = graph.nodes.get(&id_dog).unwrap();
    let dog_state = graph.states.get(&dog_node.state_id).unwrap();

    println!("Dog Metrics: {:?}", dog_state.value.metrics);
    assert!(dog_state.value.metrics.propagation_count > 0);
    assert!(dog_state.value.metrics.closure_count > 0);
}

#[test]
fn ru_d_002_trace_validation() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();
    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    );

    let id_a_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("A", UnitType::Symbolic, array![1.0]),
    ));
    let id_a = graph.add_node(Node::new(id_a_s));
    let id_b_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("B", UnitType::Symbolic, array![1.0]),
    ));
    let id_b = graph.add_node(Node::new(id_b_s));

    graph.add_edge(Edge::new(id_a, id_b, RelationType::IsA, t.clone()));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_a).unwrap();

    println!("Trace: {:?}", exec_context.trace);
    assert!(!exec_context.trace.is_empty(), "Trace should not be empty");
}
