use reasonscript_hybrid_runtime::{
    SemanticTransformationEngine, SemanticTransformationError, SemanticType, SemanticTypeError,
    SemanticTypeId, SemanticTypeRegistry, TransformationKind, TransformationPath,
    TransformationPathIrNode, TransformationResult, TransformationResultIrNode,
    TRANSFORMATION_PATH_NODE, TRANSFORMATION_RESULT_NODE,
};

fn id(value: &str) -> SemanticTypeId {
    SemanticTypeId::from(value)
}

fn transformation_engine() -> SemanticTransformationEngine {
    let mut types = SemanticTypeRegistry::new();
    types.register_type(SemanticType::root("Entity")).unwrap();
    types
        .register_type(SemanticType::child("LivingThing", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Animal", "LivingThing"))
        .unwrap();
    types
        .register_type(SemanticType::child("Dog", "Animal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Cat", "Animal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Bird", "Animal"))
        .unwrap();

    SemanticTransformationEngine::new(types)
}

#[test]
fn ste_001_generalization_one_level() {
    let result = transformation_engine().generalize(&id("Dog"), 1).unwrap();

    assert_eq!(result.target, id("Animal"));
    assert_eq!(result.kind, TransformationKind::Generalization);
    assert_eq!(result.distance, 1);
    assert_eq!(result.path.nodes, vec![id("Dog"), id("Animal")]);
}

#[test]
fn ste_002_generalization_multi_level() {
    let result = transformation_engine().generalize(&id("Dog"), 3).unwrap();

    assert_eq!(result.target, id("Entity"));
    assert_eq!(result.distance, 3);
    assert_eq!(
        result.path.nodes,
        vec![id("Dog"), id("Animal"), id("LivingThing"), id("Entity")]
    );
}

#[test]
fn ste_003_generalize_to() {
    let result = transformation_engine()
        .generalize_to(&id("Dog"), &id("Animal"))
        .unwrap();

    assert_eq!(result.target, id("Animal"));
    assert_eq!(result.kind, TransformationKind::Generalization);
    assert_eq!(result.distance, 1);
}

#[test]
fn ste_004_specialization() {
    let results = transformation_engine().specialize(&id("Animal")).unwrap();

    assert_eq!(
        results
            .iter()
            .map(|result| result.target.clone())
            .collect::<Vec<_>>(),
        vec![id("Dog"), id("Cat"), id("Bird")]
    );
    assert!(results
        .iter()
        .all(|result| result.kind == TransformationKind::Specialization));
}

#[test]
fn ste_005_specialize_to() {
    let result = transformation_engine()
        .specialize_to(&id("Animal"), &id("Dog"))
        .unwrap();

    assert_eq!(result.target, id("Dog"));
    assert_eq!(result.kind, TransformationKind::Specialization);
    assert_eq!(result.path.nodes, vec![id("Animal"), id("Dog")]);
}

#[test]
fn ste_006_transformation_path() {
    let path = transformation_engine()
        .transformation_path(&id("Dog"), &id("Entity"))
        .unwrap();

    assert_eq!(
        path.nodes,
        vec![id("Dog"), id("Animal"), id("LivingThing"), id("Entity")]
    );
}

#[test]
fn ste_007_identity_transform() {
    let engine = transformation_engine();
    let generalized = engine.generalize_to(&id("Dog"), &id("Dog")).unwrap();
    let specialized = engine.specialize_to(&id("Dog"), &id("Dog")).unwrap();
    let path = engine.transformation_path(&id("Dog"), &id("Dog")).unwrap();

    assert_eq!(generalized.distance, 0);
    assert_eq!(specialized.distance, 0);
    assert_eq!(path.nodes, vec![id("Dog")]);
}

#[test]
fn ste_008_unknown_type() {
    let engine = transformation_engine();

    assert_eq!(
        engine.generalize(&id("Unknown"), 1),
        Err(SemanticTransformationError::TypeHierarchy(
            SemanticTypeError::TypeNotFound("Unknown".to_string())
        ))
    );
    assert_eq!(
        engine.specialize_to(&id("Animal"), &id("Unknown")),
        Err(SemanticTransformationError::TypeHierarchy(
            SemanticTypeError::TypeNotFound("Unknown".to_string())
        ))
    );
}

#[test]
fn ste_009_ir_serialization() {
    let result = transformation_engine()
        .generalize_to(&id("Dog"), &id("Entity"))
        .unwrap();
    let result_ir = TransformationResultIrNode::from(&result);
    let path_ir = TransformationPathIrNode::from(&result.path);

    assert_eq!(
        serde_json::to_value(&result_ir).unwrap(),
        serde_json::json!({
            "node_type": TRANSFORMATION_RESULT_NODE,
            "source": "Dog",
            "target": "Entity",
            "kind": "Generalization",
            "distance": 3
        })
    );
    assert_eq!(
        serde_json::to_value(&path_ir).unwrap(),
        serde_json::json!({
            "node_type": TRANSFORMATION_PATH_NODE,
            "nodes": ["Dog", "Animal", "LivingThing", "Entity"]
        })
    );

    let restored_result: TransformationResult =
        serde_json::from_str(&result.to_json_pretty().unwrap()).unwrap();
    let restored_path: TransformationPath =
        serde_json::from_str(&result.path.to_json_pretty().unwrap()).unwrap();
    assert_eq!(restored_result, result);
    assert_eq!(restored_path, result.path);
}

#[test]
fn ste_010_determinism() {
    let engine = transformation_engine();
    let expected_specializations = engine.specialize(&id("Animal")).unwrap();
    let expected_path = engine
        .transformation_path(&id("Dog"), &id("Entity"))
        .unwrap();

    for _ in 0..100 {
        assert_eq!(
            engine.specialize(&id("Animal")).unwrap(),
            expected_specializations
        );
        assert_eq!(
            engine
                .transformation_path(&id("Dog"), &id("Entity"))
                .unwrap(),
            expected_path
        );
    }
}

#[test]
fn direction_and_path_failures_are_rejected() {
    let mut types = transformation_engine().type_registry().clone();
    types
        .register_type(SemanticType::child("Vehicle", "Entity"))
        .unwrap();
    let engine = SemanticTransformationEngine::new(types);

    assert!(matches!(
        engine.generalize_to(&id("Animal"), &id("Dog")),
        Err(SemanticTransformationError::InvalidDirection {
            kind: TransformationKind::Generalization,
            ..
        })
    ));
    assert!(matches!(
        engine.specialize_to(&id("Dog"), &id("Animal")),
        Err(SemanticTransformationError::InvalidDirection {
            kind: TransformationKind::Specialization,
            ..
        })
    ));
    assert!(matches!(
        engine.transformation_path(&id("Dog"), &id("Vehicle")),
        Err(SemanticTransformationError::NoTransformationPath { .. })
    ));
}

#[test]
fn generalization_cannot_exceed_root() {
    assert_eq!(
        transformation_engine().generalize(&id("Dog"), 4),
        Err(SemanticTransformationError::InvalidGeneralizationLevel {
            source: "Dog".to_string(),
            levels: 4,
            maximum: 3,
        })
    );
}

#[test]
fn specialization_paths_include_intermediate_types() {
    let result = transformation_engine()
        .specialize_to(&id("LivingThing"), &id("Dog"))
        .unwrap();

    assert_eq!(
        result.path.nodes,
        vec![id("LivingThing"), id("Animal"), id("Dog")]
    );
    assert_eq!(result.distance, 2);
}
