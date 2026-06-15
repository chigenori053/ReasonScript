use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{
    ReasonUnit, State, StructuralConstraintValidator, Transition,
};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph, ReasoningSpace, SemanticPlan};
use reasonscript_runtime_real::knowledge::{Knowledge, KnowledgeError, KnowledgeGenerator};
use reasonscript_runtime_real::semantic_simulation::{SemanticSimulation, SimulationResult};
use uuid::Uuid;

fn transition() -> Transition {
    Transition::new(
        TransitionType::Simulation,
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
    confidence: f64,
) {
    let mut edge = Edge::new(source, target, relation, transition());
    edge.confidence = confidence;
    graph.add_edge(edge);
}

fn taxonomic_space() -> (ReasoningSpace, SemanticPlan) {
    let mut graph = ReasonGraph::default();
    let dog = add_unit(&mut graph, "Dog", StateType::Concept);
    let mammal = add_unit(&mut graph, "Mammal", StateType::Concept);
    let animal = add_unit(&mut graph, "Animal", StateType::Concept);
    add_relation(&mut graph, dog, mammal, RelationType::IsA, 0.96);
    add_relation(&mut graph, mammal, animal, RelationType::IsA, 0.97);
    (
        ReasoningSpace::from_graph(graph).unwrap(),
        SemanticPlan::new(dog, animal),
    )
}

#[test]
fn core_001_semantic_unit_types_are_frozen() {
    let types = [
        StateType::Concept,
        StateType::Object,
        StateType::Event,
        StateType::Action,
        StateType::Attribute,
        StateType::Goal,
        StateType::Constraint,
    ];

    assert_eq!(types.len(), 7);
    assert!(!types.contains(&StateType::Unknown));
}

#[test]
fn core_002_semantic_relations_are_frozen() {
    let relations = [
        RelationType::IsA,
        RelationType::PartOf,
        RelationType::Cause,
        RelationType::Similar,
        RelationType::Constraint,
        RelationType::Temporal,
        RelationType::Spatial,
        RelationType::Dependency,
    ];

    assert_eq!(relations.len(), 8);
}

#[test]
fn core_003_scv_1_rejects_invalid_topology() {
    let mut graph = ReasonGraph::default();
    let event = add_unit(&mut graph, "Explosion", StateType::Event);
    let object = add_unit(&mut graph, "Car", StateType::Object);
    add_relation(&mut graph, event, object, RelationType::IsA, 1.0);

    assert!(StructuralConstraintValidator::validate_graph(&graph).is_err());
    assert!(ReasoningSpace::from_graph(graph).is_err());
}

#[test]
fn core_004_simulation_is_deterministic_and_immutable() {
    let (space, plan) = taxonomic_space();
    let before = serde_json::to_value(space.to_graph_ir()).unwrap();
    let simulation = SemanticSimulation::new();
    let expected = simulation.simulate(&space, &plan).unwrap();

    for _ in 0..100 {
        assert_eq!(simulation.simulate(&space, &plan).unwrap(), expected);
    }
    assert_eq!(serde_json::to_value(space.to_graph_ir()).unwrap(), before);
}

#[test]
fn core_005_simulation_result_preserves_trace_and_metrics() {
    let (space, plan) = taxonomic_space();
    let result = SemanticSimulation::new().simulate(&space, &plan).unwrap();

    assert_eq!(result.source_plan, plan);
    assert_eq!(result.trace.states, result.path);
    assert_eq!(result.trace.steps.len(), result.distance);
    assert_eq!(result.cost, 2.0);
    assert_eq!(result.confidence, 0.9312);
}

#[test]
fn core_006_knowledge_preserves_evidence_and_confidence() {
    let (space, plan) = taxonomic_space();
    let result = SemanticSimulation::new().simulate(&space, &plan).unwrap();
    let knowledge = KnowledgeGenerator::new().generate(&result).unwrap();

    assert_eq!(knowledge.evidence.source_plan, plan);
    assert_eq!(knowledge.evidence.simulation_result, result);
    assert_eq!(knowledge.confidence, result.confidence);
}

#[test]
fn core_007_pipeline_is_json_reproducible() {
    let (space, plan) = taxonomic_space();
    let simulation = SemanticSimulation::new();
    let result = simulation.simulate(&space, &plan).unwrap();
    let knowledge = KnowledgeGenerator::new().generate(&result).unwrap();

    let restored_result: SimulationResult =
        serde_json::from_str(&result.to_json_pretty().unwrap()).unwrap();
    let restored_knowledge: Knowledge =
        serde_json::from_str(&knowledge.to_json_pretty().unwrap()).unwrap();

    assert_eq!(restored_result, result);
    assert_eq!(restored_knowledge, knowledge);
}

#[test]
fn core_008_failed_reasoning_does_not_generate_knowledge() {
    let mut graph = ReasonGraph::default();
    let dog = add_unit(&mut graph, "Dog", StateType::Concept);
    let vehicle = add_unit(&mut graph, "Vehicle", StateType::Concept);
    let space = ReasoningSpace::from_graph(graph).unwrap();
    let result = SemanticSimulation::new()
        .simulate_goal(&space, dog, vehicle)
        .unwrap();

    assert_eq!(
        KnowledgeGenerator::new().generate(&result),
        Err(KnowledgeError::SimulationFailed)
    );
}
