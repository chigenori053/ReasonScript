use reasonscript_hybrid_runtime::{
    ConstraintKind, ConstraintPolarity, SemanticConstraint, SemanticConstraintDeclaration,
    SemanticConstraintError, SemanticConstraintId, SemanticConstraintIrNode,
    SemanticConstraintRegistry, SemanticType, SemanticTypeId, SemanticTypeRegistry,
    SEMANTIC_CONSTRAINT_NODE,
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

fn animal_hierarchy() -> SemanticTypeRegistry {
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

#[test]
fn sc_001_constraint_registration() {
    let types = animal_hierarchy();
    let mut constraints = SemanticConstraintRegistry::new();

    constraints
        .add_constraint(
            &types,
            constraint(
                "animal-alive",
                "Animal",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "alive",
            ),
        )
        .unwrap();

    assert_eq!(
        constraints.get_constraints(&types, &id("Animal")).unwrap(),
        [constraint(
            "animal-alive",
            "Animal",
            ConstraintKind::Property,
            ConstraintPolarity::Positive,
            "alive",
        )]
    );
}

#[test]
fn sc_002_unknown_type_rejection() {
    let types = animal_hierarchy();
    let mut constraints = SemanticConstraintRegistry::new();

    assert_eq!(
        constraints.add_constraint(
            &types,
            constraint(
                "unknown-alive",
                "Unknown",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "alive",
            ),
        ),
        Err(SemanticConstraintError::UnknownTargetType(
            "Unknown".to_string()
        ))
    );
}

#[test]
fn sc_003_empty_predicate_rejection() {
    let types = animal_hierarchy();
    let mut constraints = SemanticConstraintRegistry::new();

    assert_eq!(
        constraints.add_constraint(
            &types,
            constraint(
                "animal-empty",
                "Animal",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "  ",
            ),
        ),
        Err(SemanticConstraintError::InvalidPredicate("  ".to_string()))
    );
}

#[test]
fn sc_004_duplicate_rejection() {
    let types = animal_hierarchy();
    let mut constraints = SemanticConstraintRegistry::new();
    let alive = constraint(
        "animal-alive",
        "Animal",
        ConstraintKind::Property,
        ConstraintPolarity::Positive,
        "alive",
    );
    constraints.add_constraint(&types, alive.clone()).unwrap();

    assert_eq!(
        constraints.add_constraint(&types, alive),
        Err(SemanticConstraintError::DuplicateConstraintId(
            "animal-alive".to_string()
        ))
    );
    assert_eq!(
        constraints.add_constraint(
            &types,
            constraint(
                "animal-alive-copy",
                "Animal",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "alive",
            ),
        ),
        Err(SemanticConstraintError::DuplicateConstraint {
            existing_id: "animal-alive".to_string(),
            duplicate_id: "animal-alive-copy".to_string(),
        })
    );
}

#[test]
fn sc_005_constraint_lookup_returns_only_direct_constraints() {
    let types = animal_hierarchy();
    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [
            constraint(
                "animal-alive",
                "Animal",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "alive",
            ),
            constraint(
                "bird-fly",
                "Bird",
                ConstraintKind::Capability,
                ConstraintPolarity::Positive,
                "fly",
            ),
        ],
    )
    .unwrap();

    let bird = constraints.get_constraints(&types, &id("Bird")).unwrap();

    assert_eq!(bird.len(), 1);
    assert_eq!(bird[0].predicate, "fly");
}

#[test]
fn sc_006_inherited_constraint_lookup() {
    let mut types = animal_hierarchy();
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

    let effective = constraints
        .get_effective_constraints(&types, &id("Dog"))
        .unwrap();

    assert_eq!(effective.len(), 1);
    assert_eq!(effective[0].predicate, "alive");
}

#[test]
fn sc_007_multi_level_inheritance() {
    let types = animal_hierarchy();
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
                "bird-fly",
                "Bird",
                ConstraintKind::Capability,
                ConstraintPolarity::Positive,
                "fly",
            ),
        ],
    )
    .unwrap();

    let effective = constraints
        .get_effective_constraints(&types, &id("Penguin"))
        .unwrap();

    assert_eq!(
        effective
            .iter()
            .map(|constraint| constraint.predicate.as_str())
            .collect::<Vec<_>>(),
        vec!["fly", "alive", "exists"]
    );
}

#[test]
fn sc_008_positive_and_negative_constraints_coexist() {
    let types = animal_hierarchy();
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

    let effective = constraints
        .get_effective_constraints(&types, &id("Penguin"))
        .unwrap();

    assert_eq!(effective.len(), 2);
    assert_eq!(effective[0].polarity, ConstraintPolarity::Negative);
    assert_eq!(effective[1].polarity, ConstraintPolarity::Positive);
}

#[test]
fn sc_009_ast_serialize() {
    let declaration = SemanticConstraintDeclaration::new(
        "Bird",
        ConstraintKind::Capability,
        "fly",
        ConstraintPolarity::Positive,
    );

    assert_eq!(
        serde_json::to_value(&declaration).unwrap(),
        serde_json::json!({
            "node_type": "SemanticConstraint",
            "target": "Bird",
            "kind": "Capability",
            "predicate": "fly",
            "polarity": "Positive"
        })
    );

    let restored: SemanticConstraintDeclaration =
        serde_json::from_value(serde_json::to_value(&declaration).unwrap()).unwrap();
    assert_eq!(restored, declaration);
    assert_eq!(
        restored
            .into_constraint("bird-can-fly")
            .unwrap()
            .target_type,
        id("Bird")
    );
}

#[test]
fn sc_010_reason_ir_serialize() {
    let constraint = constraint(
        "bird-can-fly",
        "Bird",
        ConstraintKind::Capability,
        ConstraintPolarity::Positive,
        "fly",
    );
    let node = SemanticConstraintIrNode::from(&constraint);

    assert_eq!(node.node_type, SEMANTIC_CONSTRAINT_NODE);
    assert_eq!(
        serde_json::to_value(&node).unwrap(),
        serde_json::json!({
            "node_type": "SemanticConstraint",
            "id": "bird-can-fly",
            "target_type": "Bird",
            "kind": "Capability",
            "polarity": "Positive",
            "predicate": "fly"
        })
    );
    assert_eq!(SemanticConstraint::try_from(node).unwrap(), constraint);
}

#[test]
fn sp_2_completion_condition_derives_penguin_knowledge() {
    let types = animal_hierarchy();
    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [
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

    let penguin_knowledge = constraints
        .get_effective_constraints(&types, &id("Penguin"))
        .unwrap();

    assert!(penguin_knowledge
        .iter()
        .any(|constraint| constraint.predicate == "alive"));
    assert!(penguin_knowledge
        .iter()
        .any(|constraint| constraint.predicate == "fly"));
}

#[test]
fn all_sp_2_constraint_kinds_are_preserved() {
    let types = animal_hierarchy();
    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [
            constraint(
                "animal-alive",
                "Animal",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "alive",
            ),
            constraint(
                "animal-move",
                "Animal",
                ConstraintKind::Capability,
                ConstraintPolarity::Positive,
                "move",
            ),
            constraint(
                "animal-no-static",
                "Animal",
                ConstraintKind::Restriction,
                ConstraintPolarity::Negative,
                "static",
            ),
            constraint(
                "animal-requires-alive",
                "Animal",
                ConstraintKind::Requirement,
                ConstraintPolarity::Positive,
                "requires_alive",
            ),
        ],
    )
    .unwrap();

    assert_eq!(
        constraints
            .get_constraints(&types, &id("Animal"))
            .unwrap()
            .iter()
            .map(|constraint| constraint.kind)
            .collect::<Vec<_>>(),
        vec![
            ConstraintKind::Property,
            ConstraintKind::Capability,
            ConstraintKind::Restriction,
            ConstraintKind::Requirement,
        ]
    );
}

#[test]
fn constraint_ir_registry_round_trip() {
    let types = animal_hierarchy();
    let registry = SemanticConstraintRegistry::from_constraints(
        &types,
        [
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

    let restored =
        SemanticConstraintRegistry::from_ir_nodes(&types, registry.to_ir_nodes()).unwrap();

    assert_eq!(
        restored
            .get_effective_constraints(&types, &id("Penguin"))
            .unwrap()
            .len(),
        2
    );
}

#[test]
fn empty_constraint_id_is_rejected() {
    let types = animal_hierarchy();
    let mut constraints = SemanticConstraintRegistry::new();

    assert_eq!(
        constraints.add_constraint(
            &types,
            constraint(
                " ",
                "Animal",
                ConstraintKind::Property,
                ConstraintPolarity::Positive,
                "alive",
            ),
        ),
        Err(SemanticConstraintError::InvalidConstraintId(
            " ".to_string()
        ))
    );
}

#[test]
fn semantic_constraint_id_constructor_validates_input() {
    assert_eq!(
        SemanticConstraintId::new(""),
        Err(SemanticConstraintError::InvalidConstraintId(String::new()))
    );
    assert_eq!(
        SemanticConstraintId::new("bird-can-fly").unwrap().as_str(),
        "bird-can-fly"
    );
}
