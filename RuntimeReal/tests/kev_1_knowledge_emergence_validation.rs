use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph, ReasoningSpace, SemanticPlan};
use reasonscript_runtime_real::knowledge::{
    Knowledge, KnowledgeError, KnowledgeGenerator, SemanticRelation,
};
use reasonscript_runtime_real::semantic_simulation::{SemanticSimulation, SimulationResult};
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
    confidence: f64,
) {
    let mut edge = Edge::new(source, target, relation, transition());
    edge.confidence = confidence;
    graph.add_edge(edge);
}

fn simulate_chain(
    labels: [&str; 3],
    state_type: StateType,
    relation: RelationType,
) -> (SemanticPlan, SimulationResult, [Uuid; 3]) {
    let mut graph = ReasonGraph::default();
    let first = add_unit(&mut graph, labels[0], state_type);
    let second = add_unit(&mut graph, labels[1], state_type);
    let third = add_unit(&mut graph, labels[2], state_type);
    add_relation(&mut graph, first, second, relation, 0.96);
    add_relation(&mut graph, second, third, relation, 0.97);

    let space = ReasoningSpace::from_graph(graph).unwrap();
    let plan = SemanticPlan::new(first, third);
    let result = SemanticSimulation::new().simulate(&space, &plan).unwrap();
    (plan, result, [first, second, third])
}

#[test]
fn kev_001_taxonomic_knowledge_emerges() {
    let (_, result, [dog, _, animal]) = simulate_chain(
        ["Dog", "Mammal", "Animal"],
        StateType::Concept,
        RelationType::IsA,
    );

    let knowledge = KnowledgeGenerator::new().generate(&result).unwrap();

    assert_eq!(
        knowledge.relation,
        SemanticRelation {
            source: dog,
            target: animal,
            relation: RelationType::IsA,
        }
    );
}

#[test]
fn kev_002_part_of_knowledge_emerges() {
    let (_, result, [wheel, _, vehicle]) = simulate_chain(
        ["Wheel", "Car", "Vehicle"],
        StateType::Object,
        RelationType::PartOf,
    );

    let knowledge = KnowledgeGenerator::new().generate(&result).unwrap();

    assert_eq!(knowledge.relation.source, wheel);
    assert_eq!(knowledge.relation.target, vehicle);
    assert_eq!(knowledge.relation.relation, RelationType::PartOf);
}

#[test]
fn kev_003_causal_knowledge_emerges() {
    let (_, result, [collision, _, claim]) = simulate_chain(
        ["Collision", "Damage", "InsuranceClaim"],
        StateType::Event,
        RelationType::Cause,
    );

    let knowledge = KnowledgeGenerator::new().generate(&result).unwrap();

    assert_eq!(knowledge.relation.source, collision);
    assert_eq!(knowledge.relation.target, claim);
    assert_eq!(knowledge.relation.relation, RelationType::Cause);
}

#[test]
fn kev_004_failed_simulation_generates_no_knowledge() {
    let mut graph = ReasonGraph::default();
    let dog = add_unit(&mut graph, "Dog", StateType::Concept);
    let animal = add_unit(&mut graph, "Animal", StateType::Concept);
    let space = ReasoningSpace::from_graph(graph).unwrap();
    let result = SemanticSimulation::new()
        .simulate_goal(&space, dog, animal)
        .unwrap();

    assert_eq!(
        KnowledgeGenerator::new().generate(&result),
        Err(KnowledgeError::SimulationFailed)
    );
}

#[test]
fn kev_005_knowledge_preserves_complete_evidence_and_confidence() {
    let (plan, result, _) = simulate_chain(
        ["Dog", "Mammal", "Animal"],
        StateType::Concept,
        RelationType::IsA,
    );

    let knowledge = KnowledgeGenerator::new().generate(&result).unwrap();

    assert_eq!(knowledge.evidence.source_plan, plan);
    assert_eq!(knowledge.evidence.simulation_result, result);
    assert_eq!(knowledge.confidence, result.confidence);
    assert_eq!(
        knowledge.evidence.simulation_result.trace.states,
        result.path
    );
}

#[test]
fn kev_006_knowledge_generation_is_deterministic() {
    let (_, result, _) = simulate_chain(
        ["Dog", "Mammal", "Animal"],
        StateType::Concept,
        RelationType::IsA,
    );
    let generator = KnowledgeGenerator::new();
    let expected = generator.generate(&result).unwrap();
    let expected_json = expected.to_json_pretty().unwrap();

    for _ in 0..100 {
        let actual = generator.generate(&result).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual.to_json_pretty().unwrap(), expected_json);
    }
}

#[test]
fn kev_007_knowledge_survives_json_round_trip() {
    let (_, result, _) = simulate_chain(
        ["Dog", "Mammal", "Animal"],
        StateType::Concept,
        RelationType::IsA,
    );
    let knowledge = KnowledgeGenerator::new().generate(&result).unwrap();

    let json = knowledge.to_json_pretty().unwrap();
    let restored: Knowledge = serde_json::from_str(&json).unwrap();

    assert_eq!(restored, knowledge);
}

#[test]
fn unsupported_relations_do_not_emerge_as_knowledge() {
    let (_, result, _) = simulate_chain(
        ["Past", "Present", "Future"],
        StateType::Event,
        RelationType::Temporal,
    );

    assert_eq!(
        KnowledgeGenerator::new().generate(&result),
        Err(KnowledgeError::UnsupportedRelation(RelationType::Temporal))
    );
}

#[test]
fn emergent_relation_must_itself_satisfy_scv_1() {
    let (_, mut result, _) = simulate_chain(
        ["Action", "Event", "Attribute"],
        StateType::Event,
        RelationType::Cause,
    );
    result.trace.steps[0].source_type = StateType::Action;
    result.trace.steps[1].target_type = StateType::Attribute;

    assert_eq!(
        KnowledgeGenerator::new().generate(&result),
        Err(KnowledgeError::ScvViolation {
            relation: RelationType::Cause,
        })
    );
}

#[test]
fn zero_distance_simulation_does_not_emerge_as_knowledge() {
    let mut graph = ReasonGraph::default();
    let dog = add_unit(&mut graph, "Dog", StateType::Concept);
    let space = ReasoningSpace::from_graph(graph).unwrap();
    let result = SemanticSimulation::new()
        .simulate_goal(&space, dog, dog)
        .unwrap();

    assert_eq!(
        KnowledgeGenerator::new().generate(&result),
        Err(KnowledgeError::EmptyTrajectory)
    );
}

#[test]
fn tampered_simulation_metrics_are_rejected() {
    let (_, mut result, _) = simulate_chain(
        ["Dog", "Mammal", "Animal"],
        StateType::Concept,
        RelationType::IsA,
    );
    result.confidence = 0.5;

    assert!(matches!(
        KnowledgeGenerator::new().generate(&result),
        Err(KnowledgeError::InvalidEvidence(_))
    ));
}
