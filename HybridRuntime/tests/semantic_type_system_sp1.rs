use reasonscript_hybrid_runtime::{
    SemanticType, SemanticTypeDeclaration, SemanticTypeError, SemanticTypeId, SemanticTypeIrNode,
    SemanticTypeMetadata, SemanticTypeRegistry, IS_A_RELATION, SEMANTIC_RELATION_NODE,
    SEMANTIC_TYPE_DECLARATION_NODE, SEMANTIC_TYPE_NODE,
};

fn id(value: &str) -> SemanticTypeId {
    SemanticTypeId::from(value)
}

fn animal_hierarchy() -> SemanticTypeRegistry {
    let mut registry = SemanticTypeRegistry::new();
    registry
        .register_type(SemanticType::root("Entity"))
        .unwrap();
    registry
        .register_type(SemanticType::child("Animal", "Entity"))
        .unwrap();
    registry
        .register_type(SemanticType::child("Mammal", "Animal"))
        .unwrap();
    registry
        .register_type(SemanticType::child("Dog", "Mammal"))
        .unwrap();
    registry
}

#[test]
fn st_001_type_registration() {
    let registry = animal_hierarchy();

    assert_eq!(registry.get_type(&id("Dog")).unwrap().name, "Dog");
    registry.validate().unwrap();
}

#[test]
fn st_002_duplicate_type_rejection() {
    let mut registry = SemanticTypeRegistry::new();
    registry.register_type(SemanticType::root("Dog")).unwrap();

    assert_eq!(
        registry.register_type(SemanticType::root("Dog")),
        Err(SemanticTypeError::DuplicateType("Dog".to_string()))
    );
}

#[test]
fn st_003_unknown_parent_rejection() {
    let mut registry = SemanticTypeRegistry::new();

    assert_eq!(
        registry.register_type(SemanticType::child("Dog", "UnknownType")),
        Err(SemanticTypeError::UnknownParent("UnknownType".to_string()))
    );
}

#[test]
fn st_004_self_inheritance_rejection() {
    let mut registry = SemanticTypeRegistry::new();

    assert_eq!(
        registry.register_type(SemanticType::child("Dog", "Dog")),
        Err(SemanticTypeError::SelfInheritance("Dog".to_string()))
    );
}

#[test]
fn st_005_circular_inheritance_rejection() {
    let result = SemanticTypeRegistry::from_types([
        SemanticType::child("A", "C"),
        SemanticType::child("B", "A"),
        SemanticType::child("C", "B"),
    ]);

    assert!(matches!(
        result,
        Err(SemanticTypeError::CircularInheritance(_))
    ));
}

#[test]
fn st_006_parent_lookup() {
    let registry = animal_hierarchy();

    assert_eq!(
        registry.get_parent(&id("Dog")).map(|parent| &parent.id),
        Some(&id("Mammal"))
    );
}

#[test]
fn st_007_ancestor_lookup() {
    let registry = animal_hierarchy();

    assert_eq!(
        registry.get_ancestors(&id("Dog")).unwrap(),
        vec![id("Mammal"), id("Animal"), id("Entity")]
    );
}

#[test]
fn st_008_subtype_check() {
    let mut registry = animal_hierarchy();
    registry
        .register_type(SemanticType::child("Vehicle", "Entity"))
        .unwrap();

    assert!(registry.is_subtype_of(&id("Dog"), &id("Animal")).unwrap());
    assert!(!registry.is_subtype_of(&id("Dog"), &id("Vehicle")).unwrap());
    assert!(registry.is_subtype_of(&id("Dog"), &id("Dog")).unwrap());
}

#[test]
fn st_009_descendant_lookup() {
    let mut registry = SemanticTypeRegistry::new();
    registry
        .register_type(SemanticType::root("Animal"))
        .unwrap();
    registry
        .register_type(SemanticType::child("Dog", "Animal"))
        .unwrap();
    registry
        .register_type(SemanticType::child("Cat", "Animal"))
        .unwrap();

    assert_eq!(
        registry.get_descendants(&id("Animal")).unwrap(),
        vec![id("Dog"), id("Cat")]
    );
}

#[test]
fn st_010_semantic_is_a_derivation() {
    let registry = animal_hierarchy();

    let relations = registry.derive_is_a(&id("Dog")).unwrap();

    assert_eq!(relations.len(), 3);
    assert!(relations.iter().all(|relation| {
        relation.node_type == SEMANTIC_RELATION_NODE
            && relation.relation_type == IS_A_RELATION
            && relation.source == id("Dog")
    }));
    assert_eq!(
        relations
            .iter()
            .map(|relation| relation.target.clone())
            .collect::<Vec<_>>(),
        vec![id("Mammal"), id("Animal"), id("Entity")]
    );
    assert_eq!(
        registry.semantic_closure(&id("Dog")).unwrap(),
        vec![id("Dog"), id("Mammal"), id("Animal"), id("Entity")]
    );
}

#[test]
fn standard_semantic_types_match_sp1_hierarchy() {
    let registry = SemanticTypeRegistry::standard();

    registry.validate().unwrap();
    assert!(registry
        .is_subtype_of(&id("Concept"), &id("Entity"))
        .unwrap());
    assert!(registry
        .is_subtype_of(&id("Agent"), &id("Concrete"))
        .unwrap());
    assert!(registry.is_subtype_of(&id("Vector"), &id("Value")).unwrap());
    assert_eq!(registry.get_descendants(&id("Entity")).unwrap().len(), 15);
}

#[test]
fn semantic_ast_and_ir_fixtures_round_trip() {
    let declaration = SemanticTypeDeclaration {
        node_type: SEMANTIC_TYPE_DECLARATION_NODE.to_string(),
        name: "bio.Dog".to_string(),
        parent: Some("bio.Mammal".to_string()),
        metadata: SemanticTypeMetadata {
            description: Some("Dog semantic type".to_string()),
            declared_in: Some("animals.rsn".to_string()),
        },
    };
    let type_def = SemanticType::try_from(declaration.clone()).unwrap();
    let ir_node = SemanticTypeIrNode::from(&type_def);

    assert_eq!(ir_node.node_type, SEMANTIC_TYPE_NODE);
    assert_eq!(
        serde_json::to_value(&declaration).unwrap(),
        serde_json::json!({
            "node_type": "SemanticTypeDeclaration",
            "name": "bio.Dog",
            "parent": "bio.Mammal",
            "metadata": {
                "description": "Dog semantic type",
                "declared_in": "animals.rsn"
            }
        })
    );
    assert_eq!(
        serde_json::to_value(&ir_node).unwrap(),
        serde_json::json!({
            "node_type": "SemanticType",
            "id": "bio.Dog",
            "parent": "bio.Mammal",
            "metadata": {
                "description": "Dog semantic type",
                "declared_in": "animals.rsn"
            }
        })
    );
    assert_eq!(SemanticType::try_from(ir_node).unwrap(), type_def);
}

#[test]
fn invalid_empty_type_id_is_rejected() {
    let mut registry = SemanticTypeRegistry::new();

    assert_eq!(
        registry.register_type(SemanticType::root("  ")),
        Err(SemanticTypeError::InvalidTypeId("  ".to_string()))
    );
}
