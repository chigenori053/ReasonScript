use reasonscript_hybrid_runtime::{
    ConstraintKind, ConstraintPolarity, SemanticClosureEngine, SemanticClosureError,
    SemanticClosureIrNode, SemanticConstraint, SemanticConstraintRegistry, SemanticType,
    SemanticTypeId, SemanticTypeRegistry, SEMANTIC_CLOSURE_NODE, SEMANTIC_CLOSURE_VERSION,
};

fn id(value: &str) -> SemanticTypeId {
    SemanticTypeId::from(value)
}

fn constraint(
    constraint_id: &str,
    target_type: &str,
    kind: ConstraintKind,
    polarity: ConstraintPolarity,
    predicate: &str,
) -> SemanticConstraint {
    SemanticConstraint::new(constraint_id, target_type, kind, polarity, predicate)
}

fn penguin_types() -> SemanticTypeRegistry {
    let mut types = SemanticTypeRegistry::new();
    types.register_type(SemanticType::root("Entity")).unwrap();
    types
        .register_type(SemanticType::child("Animal", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Bird", "Animal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Penguin", "Bird"))
        .unwrap();
    types
}

fn penguin_engine() -> SemanticClosureEngine {
    let types = penguin_types();
    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [
            constraint(
                "entity-exists",
                "Entity",
                ConstraintKind::Requirement,
                ConstraintPolarity::Positive,
                "exists",
            ),
            constraint(
                "animal-alive",
                "Animal",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "alive",
            ),
            constraint(
                "bird-can-fly",
                "Bird",
                ConstraintKind::Capability,
                ConstraintPolarity::Positive,
                "fly",
            ),
        ],
    )
    .unwrap();
    SemanticClosureEngine::new(types, constraints)
}

#[test]
fn sce_001_closure_generation() {
    let mut types = SemanticTypeRegistry::new();
    types.register_type(SemanticType::root("Entity")).unwrap();
    types
        .register_type(SemanticType::child("Animal", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Dog", "Animal"))
        .unwrap();
    let engine = SemanticClosureEngine::new(types, SemanticConstraintRegistry::new());

    let closure = engine.build_closure(&id("Dog")).unwrap();

    assert_eq!(closure.types(), [id("Dog"), id("Animal"), id("Entity")]);
    assert_eq!(closure.metadata.depth, 2);
}

#[test]
fn sce_002_constraint_closure() {
    let mut types = SemanticTypeRegistry::new();
    types.register_type(SemanticType::root("Entity")).unwrap();
    types
        .register_type(SemanticType::child("Animal", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Dog", "Animal"))
        .unwrap();
    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [constraint(
            "animal-alive",
            "Animal",
            ConstraintKind::Property,
            ConstraintPolarity::Positive,
            "alive",
        )],
    )
    .unwrap();
    let engine = SemanticClosureEngine::new(types, constraints);

    let closure = engine.build_closure(&id("Dog")).unwrap();

    assert_eq!(closure.constraints().len(), 1);
    assert_eq!(closure.constraints()[0].predicate, "alive");
}

#[test]
fn sce_003_multi_level_closure() {
    let closure = penguin_engine().build_closure(&id("Penguin")).unwrap();

    assert_eq!(
        closure.types(),
        [id("Penguin"), id("Bird"), id("Animal"), id("Entity")]
    );
    assert_eq!(
        closure
            .constraints()
            .iter()
            .map(|constraint| constraint.predicate.as_str())
            .collect::<Vec<_>>(),
        vec!["fly", "alive", "exists"]
    );
    assert_eq!(closure.metadata.depth, 3);
}

#[test]
fn sce_004_unknown_type_rejection() {
    let engine = penguin_engine();

    assert_eq!(
        engine.build_closure(&id("Unknown")),
        Err(SemanticClosureError::UnknownRootType("Unknown".to_string()))
    );
}

#[test]
fn sce_005_type_ordering() {
    let closure = penguin_engine().build_closure(&id("Penguin")).unwrap();

    assert_eq!(
        closure.types,
        vec![id("Penguin"), id("Bird"), id("Animal"), id("Entity")]
    );
}

#[test]
fn sce_006_constraint_ordering() {
    let closure = penguin_engine().build_closure(&id("Penguin")).unwrap();

    assert_eq!(
        closure
            .constraints
            .iter()
            .map(|constraint| constraint.predicate.as_str())
            .collect::<Vec<_>>(),
        vec!["fly", "alive", "exists"]
    );
}

#[test]
fn sce_007_contains_type() {
    let closure = penguin_engine().build_closure(&id("Penguin")).unwrap();

    assert!(closure.contains_type(&id("Animal")));
    assert!(!closure.contains_type(&id("Vehicle")));
}

#[test]
fn sce_008_contains_constraint() {
    let closure = penguin_engine().build_closure(&id("Penguin")).unwrap();

    assert!(closure.contains_constraint("alive"));
    assert!(!closure.contains_constraint("swim"));
}

#[test]
fn sce_009_duplicate_constraint_elimination() {
    let types = penguin_types();
    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [
            constraint(
                "bird-can-fly",
                "Bird",
                ConstraintKind::Capability,
                ConstraintPolarity::Positive,
                "fly",
            ),
            constraint(
                "animal-can-fly",
                "Animal",
                ConstraintKind::Capability,
                ConstraintPolarity::Positive,
                "fly",
            ),
        ],
    )
    .unwrap();
    let engine = SemanticClosureEngine::new(types, constraints);

    let closure = engine.build_closure(&id("Penguin")).unwrap();

    assert_eq!(closure.constraints.len(), 1);
    assert_eq!(closure.constraints[0].id.0, "bird-can-fly");
}

#[test]
fn sce_010_closure_determinism() {
    let engine = penguin_engine();
    let expected = engine.build_closure(&id("Penguin")).unwrap();
    let expected_json = expected.to_json_pretty().unwrap();

    for _ in 0..100 {
        let actual = engine.build_closure(&id("Penguin")).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual.to_json_pretty().unwrap(), expected_json);
    }
}

#[test]
fn semantic_closure_ir_serialization_preserves_order_and_details() {
    let closure = penguin_engine().build_closure(&id("Penguin")).unwrap();
    let ir = SemanticClosureIrNode::from(&closure);
    let value = serde_json::to_value(&ir).unwrap();

    assert_eq!(ir.node_type, SEMANTIC_CLOSURE_NODE);
    assert_eq!(ir.version, SEMANTIC_CLOSURE_VERSION);
    assert_eq!(
        value["types"],
        serde_json::json!(["Penguin", "Bird", "Animal", "Entity"])
    );
    assert_eq!(value["constraints"][0]["predicate"], "fly");
    assert_eq!(value["constraints"][1]["predicate"], "alive");
    assert_eq!(value["constraints"][2]["predicate"], "exists");
    assert_eq!(value["metadata"]["depth"], 3);

    let restored: SemanticClosureIrNode = serde_json::from_value(value).unwrap();
    assert_eq!(restored, ir);
}

#[test]
fn positive_and_negative_constraints_remain_distinct_in_closure() {
    let types = penguin_types();
    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [
            constraint(
                "bird-can-fly",
                "Bird",
                ConstraintKind::Capability,
                ConstraintPolarity::Positive,
                "fly",
            ),
            constraint(
                "penguin-cannot-fly",
                "Penguin",
                ConstraintKind::Capability,
                ConstraintPolarity::Negative,
                "fly",
            ),
        ],
    )
    .unwrap();
    let closure = SemanticClosureEngine::new(types, constraints)
        .build_closure(&id("Penguin"))
        .unwrap();

    assert_eq!(closure.constraints.len(), 2);
    assert_eq!(
        closure
            .constraints
            .iter()
            .map(|constraint| constraint.polarity)
            .collect::<Vec<_>>(),
        vec![ConstraintPolarity::Negative, ConstraintPolarity::Positive]
    );
}
