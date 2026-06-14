use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, SemanticContext, State, Transition};
use reasonscript_runtime_real::graph::{
    Edge, Node, ReasonGraph, ReasoningSpace, ReasoningSpaceError, SemanticPlan,
};
use reasonscript_runtime_real::ir::GraphIR;
use uuid::Uuid;

fn transition(transition_type: TransitionType) -> Transition {
    Transition::new(
        transition_type,
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

fn dog_reasoning_space() -> (ReasoningSpace, Uuid, Uuid, Uuid) {
    let mut graph = ReasonGraph::default();
    let dog = add_unit(&mut graph, "Dog", StateType::Concept);
    let mammal = add_unit(&mut graph, "Mammal", StateType::Concept);
    let animal = add_unit(&mut graph, "Animal", StateType::Concept);
    graph.add_edge(Edge::new(
        dog,
        mammal,
        RelationType::IsA,
        transition(TransitionType::Deduction),
    ));
    graph.add_edge(Edge::new(
        mammal,
        animal,
        RelationType::IsA,
        transition(TransitionType::Deduction),
    ));

    (
        ReasoningSpace::from_graph(graph).unwrap(),
        dog,
        mammal,
        animal,
    )
}

#[test]
fn rs_001_reasoning_space_accepts_a_valid_semantic_graph() {
    let (space, _, _, _) = dog_reasoning_space();

    assert_eq!(space.semantic_unit_count(), 3);
    assert_eq!(space.semantic_relation_count(), 2);
    assert_eq!(space.semantic_transition_count(), 2);
    space.validate(&SemanticContext::new(0.5)).unwrap();
}

#[test]
fn rs_002_reasoning_space_rejects_an_invalid_semantic_graph() {
    let mut graph = ReasonGraph::default();
    let event = add_unit(&mut graph, "Explosion", StateType::Event);
    let object = add_unit(&mut graph, "Car", StateType::Object);
    graph.add_edge(Edge::new(
        event,
        object,
        RelationType::IsA,
        transition(TransitionType::Deduction),
    ));

    assert!(matches!(
        ReasoningSpace::from_graph(graph),
        Err(ReasoningSpaceError::InvalidStructure(_))
    ));
}

#[test]
fn rs_003_reasoning_space_is_not_a_knowledge_graph() {
    let graph = ReasonGraph::new(GraphType::KnowledgeGraph);

    assert!(matches!(
        ReasoningSpace::from_graph(graph),
        Err(ReasoningSpaceError::InvalidGraphType(
            GraphType::KnowledgeGraph
        ))
    ));
}

#[test]
fn rs_004_exploration_discovers_reachable_semantic_states() {
    let (space, dog, mammal, animal) = dog_reasoning_space();

    let result = space.explore(dog).unwrap();

    assert_eq!(result.start, dog);
    assert_eq!(result.reachable_nodes, vec![mammal, animal]);
}

#[test]
fn rs_005_semantic_plan_is_executed_against_the_space() {
    let (space, dog, mammal, animal) = dog_reasoning_space();
    let initial_relations = space.semantic_relation_count();

    let path = space.execute_plan(&SemanticPlan::new(dog, animal)).unwrap();

    assert_eq!(path.nodes, vec![dog, mammal, animal]);
    assert_eq!(path.distance(), 2);
    assert_eq!(space.semantic_relation_count(), initial_relations);
}

#[test]
fn rs_006_missing_plan_node_returns_a_typed_error() {
    let (space, dog, _, _) = dog_reasoning_space();
    let missing = Uuid::new_v4();

    assert_eq!(
        space.execute_plan(&SemanticPlan::new(dog, missing)),
        Err(ReasoningSpaceError::NodeNotFound(missing))
    );
}

#[test]
fn rs_007_unreachable_goal_returns_a_typed_error() {
    let mut graph = ReasonGraph::default();
    let dog = add_unit(&mut graph, "Dog", StateType::Concept);
    let animal = add_unit(&mut graph, "Animal", StateType::Concept);
    let vehicle = add_unit(&mut graph, "Vehicle", StateType::Concept);
    graph.add_edge(Edge::new(
        dog,
        animal,
        RelationType::IsA,
        transition(TransitionType::Deduction),
    ));
    let space = ReasoningSpace::from_graph(graph).unwrap();

    assert_eq!(
        space.execute_plan(&SemanticPlan::new(dog, vehicle)),
        Err(ReasoningSpaceError::GoalUnreachable {
            start: dog,
            goal: vehicle,
        })
    );
}

#[test]
fn rs_008_closure_generates_valid_emergent_relations() {
    let (mut space, dog, _, animal) = dog_reasoning_space();

    let result = space.close(&SemanticContext::new(0.5)).unwrap();

    assert_eq!(result.generated_relations, 1);
    assert!(space.graph().edges.iter().any(|edge| {
        edge.source == dog && edge.target == animal && edge.relation == RelationType::IsA
    }));
    space.validate(&SemanticContext::new(0.5)).unwrap();
}

#[test]
fn rs_009_closure_does_not_generate_an_scv_invalid_causal_relation() {
    let mut graph = ReasonGraph::default();
    let run = add_unit(&mut graph, "Run", StateType::Action);
    let fatigue = add_unit(&mut graph, "Fatigue", StateType::Event);
    let exhausted = add_unit(&mut graph, "Exhausted", StateType::Attribute);
    graph.add_edge(Edge::new(
        run,
        fatigue,
        RelationType::Cause,
        transition(TransitionType::Deduction),
    ));
    graph.add_edge(Edge::new(
        fatigue,
        exhausted,
        RelationType::Cause,
        transition(TransitionType::Deduction),
    ));
    let mut space = ReasoningSpace::from_graph(graph).unwrap();

    let result = space.close(&SemanticContext::new(0.5)).unwrap();

    assert_eq!(result.generated_relations, 0);
    assert!(!space.graph().edges.iter().any(|edge| {
        edge.source == run && edge.target == exhausted && edge.relation == RelationType::Cause
    }));
}

#[test]
fn rs_010_graph_ir_is_the_canonical_serializable_representation() {
    let (space, _, _, _) = dog_reasoning_space();

    let graph_ir = space.to_graph_ir();
    let serialized = serde_json::to_string(&graph_ir).unwrap();
    let restored: GraphIR = serde_json::from_str(&serialized).unwrap();
    let restored_space = ReasoningSpace::from_graph(restored.graph).unwrap();

    assert_eq!(
        restored_space.semantic_unit_count(),
        space.semantic_unit_count()
    );
    assert_eq!(
        restored_space.semantic_relation_count(),
        space.semantic_relation_count()
    );
}

#[test]
fn rs_011_all_transition_kinds_can_be_represented_in_a_reasoning_space() {
    let transition_types = [
        TransitionType::Deduction,
        TransitionType::Induction,
        TransitionType::Abduction,
        TransitionType::Search,
        TransitionType::Simulation,
        TransitionType::Optimization,
    ];

    for transition_type in transition_types {
        let mut graph = ReasonGraph::default();
        let source = add_unit(&mut graph, "Source", StateType::Concept);
        let target = add_unit(&mut graph, "Target", StateType::Concept);
        graph.add_edge(Edge::new(
            source,
            target,
            RelationType::Similar,
            transition(transition_type),
        ));

        let space = ReasoningSpace::from_graph(graph).unwrap();
        assert_eq!(
            space.graph().edges[0].transition.transition_type,
            transition_type
        );
    }
}
