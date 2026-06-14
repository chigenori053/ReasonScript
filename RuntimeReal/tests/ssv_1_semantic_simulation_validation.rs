use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{
    Edge, Node, ReasonGraph, ReasoningSpace, SemanticPlan, SemanticPlanConstraints,
};
use reasonscript_runtime_real::semantic_simulation::{
    SemanticSimulation, SemanticSimulationError, SimulationResult,
};
use uuid::Uuid;

fn transition() -> Transition {
    Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    )
}

fn add_unit(graph: &mut ReasonGraph, label: &str, state_type: StateType) -> Uuid {
    let state = graph.add_state(State::new(
        state_type,
        ReasonUnit::new(label, UnitType::Symbolic, array![1.0]),
    ));
    graph.add_node(Node::new(state))
}

fn add_relation(
    graph: &mut ReasonGraph,
    source: Uuid,
    target: Uuid,
    relation: RelationType,
    cost: f64,
    confidence: f64,
) {
    let mut edge = Edge::new(source, target, relation, transition());
    edge.cost = cost;
    edge.confidence = confidence;
    graph.add_edge(edge);
}

fn dog_space() -> (ReasoningSpace, Uuid, Uuid, Uuid) {
    let mut graph = ReasonGraph::default();
    let dog = add_unit(&mut graph, "Dog", StateType::Concept);
    let mammal = add_unit(&mut graph, "Mammal", StateType::Concept);
    let animal = add_unit(&mut graph, "Animal", StateType::Concept);
    add_relation(&mut graph, dog, mammal, RelationType::IsA, 1.0, 0.9);
    add_relation(&mut graph, mammal, animal, RelationType::IsA, 1.5, 0.8);
    (
        ReasoningSpace::from_graph(graph).unwrap(),
        dog,
        mammal,
        animal,
    )
}

#[test]
fn ssv_001_reachable_goal_produces_a_successful_trajectory() {
    let (space, dog, mammal, animal) = dog_space();

    let result = SemanticSimulation::new()
        .simulate(&space, &SemanticPlan::new(dog, animal))
        .unwrap();

    assert!(result.success);
    assert_eq!(result.path, vec![dog, mammal, animal]);
    assert_eq!(result.distance, 2);
    assert_eq!(result.cost, 2.5);
    assert!((result.confidence - 0.72).abs() < f64::EPSILON);
}

#[test]
fn ssv_002_unreachable_goal_produces_an_unsuccessful_result() {
    let (space, dog, _, _) = dog_space();
    let mut graph = space.into_graph();
    let vehicle = add_unit(&mut graph, "Vehicle", StateType::Concept);
    let space = ReasoningSpace::from_graph(graph).unwrap();

    let result = SemanticSimulation::new()
        .simulate_goal(&space, dog, vehicle)
        .unwrap();

    assert!(!result.success);
    assert_eq!(result.path, vec![dog]);
    assert_eq!(result.distance, 0);
    assert_eq!(result.cost, 0.0);
    assert_eq!(result.confidence, 0.0);
}

#[test]
fn ssv_003_repeated_simulation_is_deterministic_and_reproducible() {
    let (space, dog, _, animal) = dog_space();
    let simulation = SemanticSimulation::new();
    let plan = SemanticPlan::new(dog, animal);
    let expected = simulation.simulate(&space, &plan).unwrap();
    let expected_json = expected.to_json_pretty().unwrap();

    for _ in 0..100 {
        let actual = simulation.simulate(&space, &plan).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual.to_json_pretty().unwrap(), expected_json);
    }

    let restored: SimulationResult = serde_json::from_str(&expected_json).unwrap();
    assert_eq!(restored, expected);
}

#[test]
fn ssv_004_simulation_rejects_an_scv_invalid_graph() {
    let mut graph = ReasonGraph::default();
    let explosion = add_unit(&mut graph, "Explosion", StateType::Event);
    let car = add_unit(&mut graph, "Car", StateType::Object);
    add_relation(&mut graph, explosion, car, RelationType::IsA, 1.0, 1.0);

    assert!(matches!(
        SemanticSimulation::new().simulate_graph(&graph, &SemanticPlan::new(explosion, car)),
        Err(SemanticSimulationError::InvalidReasoningSpace(_))
    ));
}

#[test]
fn ssv_005_trace_is_complete_for_every_path_state_and_transition() {
    let (space, dog, mammal, animal) = dog_space();

    let result = SemanticSimulation::new()
        .simulate_goal(&space, dog, animal)
        .unwrap();

    assert_eq!(result.trace.states, result.path);
    assert_eq!(result.trace.states.len(), result.path.len());
    assert_eq!(result.trace.steps.len(), result.distance);
    assert_eq!(result.trace.steps[0].source, dog);
    assert_eq!(result.trace.steps[0].target, mammal);
    assert_eq!(result.trace.steps[1].target, animal);
}

#[test]
fn ssv_006_predict_returns_future_semantic_states() {
    let (space, dog, mammal, animal) = dog_space();

    let predicted = SemanticSimulation::new().predict(&space, dog).unwrap();

    assert_eq!(predicted, vec![mammal, animal]);
}

#[test]
fn ssv_007_simulation_does_not_mutate_the_reasoning_space() {
    let (space, dog, _, animal) = dog_space();
    let before = serde_json::to_value(space.to_graph_ir()).unwrap();

    SemanticSimulation::new()
        .simulate_goal(&space, dog, animal)
        .unwrap();

    let after = serde_json::to_value(space.to_graph_ir()).unwrap();
    assert_eq!(after, before);
}

#[test]
fn plan_constraints_are_applied_during_simulation() {
    let (space, dog, mammal, animal) = dog_space();
    let constraints = SemanticPlanConstraints {
        avoid_nodes: vec![mammal],
        max_distance: None,
    };

    let result = SemanticSimulation::new()
        .simulate_goal_with_constraints(&space, dog, animal, constraints)
        .unwrap();

    assert!(!result.success);
}

#[test]
fn invalid_cost_or_confidence_is_rejected() {
    let (space, dog, _, animal) = dog_space();
    let mut graph = space.into_graph();
    graph.edges[0].confidence = 1.5;
    let space = ReasoningSpace::from_graph(graph).unwrap();

    assert!(matches!(
        SemanticSimulation::new().simulate_goal(&space, dog, animal),
        Err(SemanticSimulationError::InvalidEdgeConfidence { .. })
    ));
}
