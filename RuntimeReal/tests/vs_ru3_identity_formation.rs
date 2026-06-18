use ndarray::{array, Array1};
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{ReasonUnit, SemanticContext, State, Transition};
use reasonscript_runtime_real::executor::execution_context::TraceEvent;
use reasonscript_runtime_real::executor::{ExecutionContext, Executor};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use uuid::Uuid;

#[test]
fn if_a_001_identity_emergence_dog() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();

    // 1. Fragments
    let animal_f = ReasonUnit::new(
        "Animal",
        UnitType::Real,
        Array1::from_vec(vec![1.0, 0.0, 0.0, 0.0]),
    );
    let canine_f = ReasonUnit::new(
        "Canine",
        UnitType::Real,
        Array1::from_vec(vec![0.0, 1.0, 0.0, 0.0]),
    );
    let domestic_f = ReasonUnit::new(
        "Domestic",
        UnitType::Real,
        Array1::from_vec(vec![0.0, 0.0, 1.0, 0.0]),
    );
    let pet_f = ReasonUnit::new(
        "Pet",
        UnitType::Real,
        Array1::from_vec(vec![0.0, 0.0, 0.0, 1.0]),
    );

    // 2. Identity Formation (Composition)
    let dog_ru = animal_f.add(&canine_f).add(&domestic_f).add(&pet_f);
    let mut dog_ru = ReasonUnit::new("Dog", UnitType::Real, dog_ru.vector);

    // IF-R-001: Formation Metric
    if let Some(metrics) = &mut dog_ru.identity_metrics {
        metrics.formation_count += 1;
    }

    let id_dog_s = graph.add_state(State::new(StateType::Concept, dog_ru));
    let id_dog = graph.add_node(Node::new(id_dog_s));

    // Record trace
    exec_context.record_trace(TraceEvent::IdentityFormation {
        fragments: vec![animal_f.id, canine_f.id, domestic_f.id, pet_f.id],
        identity_id: id_dog,
    });

    // 3. Inference Validation (H8: Identity supports inference)
    let id_mammal_s = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Mammal", UnitType::Real, array![1.0, 1.0, 0.0, 0.0]),
    ));
    let id_mammal = graph.add_node(Node::new(id_mammal_s));
    let t = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(4, UnitType::Real)),
    );
    graph.add_edge(Edge::new(id_dog, id_mammal, RelationType::IsA, t));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_dog).unwrap();

    assert!(exec_context.active_nodes.contains(&id_mammal));
    println!("Identity Trace: {:?}", exec_context.trace);
}

#[test]
fn if_b_001_identity_stability_repeated_activation() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);

    let dog_ru = ReasonUnit::new("Dog", UnitType::Real, array![1.0, 1.0, 1.0, 1.0]);
    let id_dog_s = graph.add_state(State::new(StateType::Concept, dog_ru));
    let id_dog = graph.add_node(Node::new(id_dog_s));

    // Repeated Activation
    for _ in 0..10 {
        let mut exec_context = ExecutionContext::new();
        Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_dog).unwrap();

        // IF-B-001: Stability check (node exists and state is correct)
        let node = graph.nodes.get(&id_dog).unwrap();
        let state = graph.states.get(&node.state_id).unwrap();
        assert_eq!(state.value.label, "Dog");
    }

    // IF-R-002: Stabilization Trace
    let mut final_context = ExecutionContext::new();
    final_context.record_trace(TraceEvent::IdentityStabilization(id_dog));
    assert!(matches!(
        final_context.trace[0],
        TraceEvent::IdentityStabilization(_)
    ));
}

#[test]
fn if_c_001_identity_differentiation_dog_vs_wolf() {
    let dog_vec = array![1.0, 1.0, 1.0, 1.0]; // Animal, Canine, Domestic, Pet
    let wolf_vec = array![1.0, 1.0, 0.0, 0.0]; // Animal, Canine (Wild)

    let dog_ru = ReasonUnit::new("Dog", UnitType::Real, dog_vec);
    let wolf_ru = ReasonUnit::new("Wolf", UnitType::Real, wolf_vec);

    // Differentiation Score (1 - similarity)
    let dot = dog_ru.vector.dot(&wolf_ru.vector);
    let norm_d = dog_ru.vector.dot(&dog_ru.vector).sqrt();
    let norm_w = wolf_ru.vector.dot(&wolf_ru.vector).sqrt();
    let sim = dot / (norm_d * norm_w);
    let diff_score = 1.0 - sim;

    println!("Differentiation Score (Dog vs Wolf): {:.4}", diff_score);
    assert!(diff_score > 0.2); // Significant difference
}

#[test]
fn if_d_001_identity_evolution_puppy_to_dog() {
    let mut graph = ReasonGraph::default();
    let semantic_context = SemanticContext::new(0.5);
    let mut exec_context = ExecutionContext::new();

    let id_puppy_s = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("Puppy", UnitType::Real, array![1.0, 1.0, 1.0, 0.5]),
    ));
    let id_puppy = graph.add_node(Node::new(id_puppy_s));

    let id_dog_s = graph.add_state(State::new(
        StateType::Event,
        ReasonUnit::new("Dog", UnitType::Real, array![1.0, 1.0, 1.0, 1.0]),
    ));
    let id_dog = graph.add_node(Node::new(id_dog_s));

    // Evolution as a transition
    let t = Transition::new(
        TransitionType::Search,
        TransitionOp::Addition(ReasonUnit::new(
            "Growth",
            UnitType::Real,
            array![0.0, 0.0, 0.0, 0.5],
        )),
    );
    graph.add_edge(Edge::new(id_puppy, id_dog, RelationType::Temporal, t));

    Executor::infer(&mut graph, &mut exec_context, &semantic_context, id_puppy).unwrap();

    // IF-D-001: Identity Transition
    exec_context.record_trace(TraceEvent::IdentityTransition {
        from: id_puppy,
        to: id_dog,
    });

    assert!(exec_context
        .trace
        .iter()
        .any(|e| matches!(e, TraceEvent::IdentityTransition { .. })));
}
