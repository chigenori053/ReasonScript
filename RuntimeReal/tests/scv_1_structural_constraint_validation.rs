use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{
    ReasonUnit, SemanticContext, SemanticError, SemanticValidator, State,
    StructuralConstraintError, StructuralConstraintValidator, Transition,
};
use reasonscript_runtime_real::executor::executor::InferenceError;
use reasonscript_runtime_real::executor::{ExecutionContext, Executor};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use uuid::Uuid;

fn transition() -> Transition {
    Transition::new(
        TransitionType::Deduction,
        TransitionOp::Addition(ReasonUnit::zero(1, UnitType::Symbolic)),
    )
}

fn graph_with_relation(
    source_label: &str,
    source_type: StateType,
    relation: RelationType,
    target_label: &str,
    target_type: StateType,
) -> (ReasonGraph, Uuid) {
    let mut graph = ReasonGraph::default();
    let source_state = graph.add_state(State::new(
        source_type,
        ReasonUnit::new(source_label, UnitType::Symbolic, array![1.0]),
    ));
    let target_state = graph.add_state(State::new(
        target_type,
        ReasonUnit::new(target_label, UnitType::Symbolic, array![1.0]),
    ));
    let source = graph.add_node(Node::new(source_state));
    let target = graph.add_node(Node::new(target_state));
    graph.add_edge(Edge::new(source, target, relation, transition()));
    (graph, source)
}

#[test]
fn scv_001_concept_is_a_concept_passes() {
    let (graph, _) = graph_with_relation(
        "Dog",
        StateType::Concept,
        RelationType::IsA,
        "Animal",
        StateType::Concept,
    );

    assert_eq!(
        StructuralConstraintValidator::validate_graph(&graph),
        Ok(())
    );
}

#[test]
fn scv_002_object_is_a_concept_passes() {
    let (graph, _) = graph_with_relation(
        "Pochi",
        StateType::Object,
        RelationType::IsA,
        "Dog",
        StateType::Concept,
    );

    assert_eq!(
        StructuralConstraintValidator::validate_graph(&graph),
        Ok(())
    );
}

#[test]
fn scv_003_event_is_a_object_fails() {
    let (graph, _) = graph_with_relation(
        "Explosion",
        StateType::Event,
        RelationType::IsA,
        "Car",
        StateType::Object,
    );

    assert!(matches!(
        StructuralConstraintValidator::validate_graph(&graph),
        Err(StructuralConstraintError::InvalidRelation {
            source_type: StateType::Event,
            relation: RelationType::IsA,
            target_type: StateType::Object,
            ..
        })
    ));
}

#[test]
fn scv_004_goal_part_of_attribute_fails() {
    let (graph, _) = graph_with_relation(
        "ReachGoal",
        StateType::Goal,
        RelationType::PartOf,
        "Fast",
        StateType::Attribute,
    );

    assert!(matches!(
        StructuralConstraintValidator::validate_graph(&graph),
        Err(StructuralConstraintError::InvalidRelation {
            source_type: StateType::Goal,
            relation: RelationType::PartOf,
            target_type: StateType::Attribute,
            ..
        })
    ));
}

#[test]
fn scv_005_constraint_to_action_passes() {
    let (graph, _) = graph_with_relation(
        "MustNotCollide",
        StateType::Constraint,
        RelationType::Constraint,
        "Move",
        StateType::Action,
    );

    assert_eq!(
        StructuralConstraintValidator::validate_graph(&graph),
        Ok(())
    );
}

#[test]
fn scv_006_missing_node_fails() {
    let mut graph = ReasonGraph::default();
    let target_state = graph.add_state(State::new(
        StateType::Concept,
        ReasonUnit::new("Animal", UnitType::Symbolic, array![1.0]),
    ));
    let target = graph.add_node(Node::new(target_state));
    let missing_source = Uuid::new_v4();
    graph.add_edge(Edge::new(
        missing_source,
        target,
        RelationType::IsA,
        transition(),
    ));

    assert!(matches!(
        StructuralConstraintValidator::validate_graph(&graph),
        Err(StructuralConstraintError::MissingSourceNode {
            node_id,
            ..
        }) if node_id == missing_source
    ));
}

#[test]
fn scv_007_undefined_relation_fails_deserialization() {
    let (graph, _) = graph_with_relation(
        "Dog",
        StateType::Concept,
        RelationType::IsA,
        "Animal",
        StateType::Concept,
    );
    let mut value = serde_json::to_value(graph).unwrap();
    value["edges"][0]["relation"] = serde_json::json!("UndefinedRelation");

    let error = serde_json::from_value::<ReasonGraph>(value).unwrap_err();
    assert!(error.to_string().contains("unknown variant"));
}

#[test]
fn similar_requires_the_same_semantic_unit_type() {
    let (graph, _) = graph_with_relation(
        "Dog",
        StateType::Concept,
        RelationType::Similar,
        "Pochi",
        StateType::Object,
    );

    assert!(matches!(
        StructuralConstraintValidator::validate_graph(&graph),
        Err(StructuralConstraintError::InvalidRelation {
            relation: RelationType::Similar,
            ..
        })
    ));
}

#[test]
fn every_node_must_reference_an_existing_typed_state() {
    let mut graph = ReasonGraph::default();
    let node = graph.add_node(Node::new(Uuid::new_v4()));

    assert!(matches!(
        StructuralConstraintValidator::validate_graph(&graph),
        Err(StructuralConstraintError::MissingState { node_id, .. }) if node_id == node
    ));
}

#[test]
fn executor_returns_invalid_structure_before_execution() {
    let (mut graph, source) = graph_with_relation(
        "Explosion",
        StateType::Event,
        RelationType::IsA,
        "Car",
        StateType::Object,
    );
    let semantic_context = SemanticContext::new(0.5);
    let mut execution_context = ExecutionContext::new();

    let error = Executor::infer(
        &mut graph,
        &mut execution_context,
        &semantic_context,
        source,
    )
    .unwrap_err();

    assert!(matches!(
        error,
        InferenceError::SemanticError(SemanticError::InvalidStructure(_))
    ));
    assert_eq!(execution_context.timestamp, 0);
    assert!(execution_context.active_nodes.is_empty());
}

#[test]
fn semantic_validator_runs_scv_before_context_validation() {
    let (graph, _) = graph_with_relation(
        "ReachGoal",
        StateType::Goal,
        RelationType::PartOf,
        "Fast",
        StateType::Attribute,
    );

    assert!(matches!(
        SemanticValidator::validate_graph(&graph, &SemanticContext::new(0.5)),
        Err(SemanticError::InvalidStructure(_))
    ));
}
