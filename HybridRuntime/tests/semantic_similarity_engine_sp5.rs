use reasonscript_hybrid_runtime::{
    ConstraintKind, ConstraintPolarity, SemanticClosureEngine, SemanticConstraint,
    SemanticConstraintRegistry, SemanticSimilarityEngine, SemanticSimilarityError, SemanticType,
    SemanticTypeId, SemanticTypeRegistry, SimilarityReport, SimilarityReportIrNode,
    SimilarityResult, SimilarityResultIrNode, SEMANTIC_SIMILARITY_VERSION, SIMILARITY_REPORT_NODE,
    SIMILARITY_RESULT_NODE,
};

fn id(value: &str) -> SemanticTypeId {
    SemanticTypeId::from(value)
}

fn constraint(constraint_id: &str, target_type: &str, predicate: &str) -> SemanticConstraint {
    SemanticConstraint::new(
        constraint_id,
        target_type,
        ConstraintKind::Property,
        ConstraintPolarity::Positive,
        predicate,
    )
}

fn similarity_engine() -> SemanticSimilarityEngine {
    let mut types = SemanticTypeRegistry::new();
    types.register_type(SemanticType::root("Entity")).unwrap();
    types
        .register_type(SemanticType::child("Animal", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Canine", "Animal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Mammal", "Animal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Dog", "Canine"))
        .unwrap();
    types
        .register_type(SemanticType::child("Wolf", "Canine"))
        .unwrap();
    types
        .register_type(SemanticType::child("Fox", "Canine"))
        .unwrap();
    types
        .register_type(SemanticType::child("Cat", "Mammal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Bird", "Animal"))
        .unwrap();

    let constraints = SemanticConstraintRegistry::from_constraints(
        &types,
        [
            constraint("animal-alive", "Animal", "alive"),
            constraint("animal-move", "Animal", "move"),
            constraint("dog-eat", "Dog", "eat"),
            constraint("dog-domesticated", "Dog", "domesticated"),
            constraint("dog-social", "Dog", "social"),
            constraint("dog-warm", "Dog", "warm"),
            constraint("wolf-eat", "Wolf", "eat"),
            constraint("wolf-domesticated", "Wolf", "domesticated"),
            constraint("wolf-hunt", "Wolf", "hunt"),
            constraint("wolf-social", "Wolf", "social"),
            constraint("wolf-warm", "Wolf", "warm"),
            constraint("fox-eat", "Fox", "eat"),
            constraint("fox-hunt", "Fox", "hunt"),
            constraint("fox-domesticated", "Fox", "domesticated"),
            constraint("fox-social", "Fox", "social"),
            constraint("cat-domesticated", "Cat", "domesticated"),
            constraint("cat-eat", "Cat", "eat"),
            constraint("cat-purr", "Cat", "purr"),
            constraint("cat-warm", "Cat", "warm"),
            constraint("bird-fly", "Bird", "fly"),
        ],
    )
    .unwrap();

    SemanticSimilarityEngine::new(SemanticClosureEngine::new(types, constraints))
}

#[test]
fn sse_001_self_similarity() {
    let result = similarity_engine()
        .similarity(&id("Dog"), &id("Dog"))
        .unwrap();

    assert_eq!(result.similarity, 1.0);
    assert_eq!(result.type_similarity, 1.0);
    assert_eq!(result.constraint_similarity, 1.0);
}

#[test]
fn sse_002_symmetry() {
    let engine = similarity_engine();

    let dog_wolf = engine.similarity(&id("Dog"), &id("Wolf")).unwrap();
    let wolf_dog = engine.similarity(&id("Wolf"), &id("Dog")).unwrap();

    assert_eq!(dog_wolf.similarity, wolf_dog.similarity);
    assert_eq!(dog_wolf.type_similarity, wolf_dog.type_similarity);
    assert_eq!(
        dog_wolf.constraint_similarity,
        wolf_dog.constraint_similarity
    );
}

#[test]
fn sse_003_semantic_distance() {
    let engine = similarity_engine();

    assert_eq!(engine.distance(&id("Dog"), &id("Dog")).unwrap(), 0);
    assert_eq!(engine.distance(&id("Dog"), &id("Wolf")).unwrap(), 2);
    assert_eq!(engine.distance(&id("Dog"), &id("Bird")).unwrap(), 3);
}

#[test]
fn sse_004_constraint_similarity_uses_jaccard() {
    let result = similarity_engine()
        .similarity(&id("Dog"), &id("Wolf"))
        .unwrap();

    assert_eq!(result.constraint_similarity, 6.0 / 7.0);
    assert_eq!(result.type_similarity, 1.0 / 3.0);
    assert_eq!(result.similarity, 0.5 * (1.0 / 3.0) + 0.5 * (6.0 / 7.0));
}

#[test]
fn sse_005_similarity_ranking() {
    let report = similarity_engine()
        .nearest_neighbors(&id("Dog"), 8)
        .unwrap();
    let ranked = report
        .neighbors
        .iter()
        .map(|result| result.right.as_str())
        .collect::<Vec<_>>();

    let wolf = ranked
        .iter()
        .position(|type_id| *type_id == "Wolf")
        .unwrap();
    let fox = ranked.iter().position(|type_id| *type_id == "Fox").unwrap();
    let cat = ranked.iter().position(|type_id| *type_id == "Cat").unwrap();
    let bird = ranked
        .iter()
        .position(|type_id| *type_id == "Bird")
        .unwrap();

    assert!(wolf < fox);
    assert!(fox < cat);
    assert!(cat < bird);
}

#[test]
fn sse_006_nearest_neighbor_limit() {
    let report = similarity_engine()
        .nearest_neighbors(&id("Dog"), 3)
        .unwrap();

    assert_eq!(report.neighbors.len(), 3);
    assert_eq!(
        report
            .neighbors
            .iter()
            .map(|result| result.right.as_str())
            .collect::<Vec<_>>(),
        vec!["Wolf", "Fox", "Cat"]
    );

    let empty = similarity_engine()
        .nearest_neighbors(&id("Dog"), 0)
        .unwrap();
    assert!(empty.neighbors.is_empty());
}

#[test]
fn sse_007_unknown_type_rejection() {
    let engine = similarity_engine();

    assert!(matches!(
        engine.similarity(&id("Dog"), &id("Unknown")),
        Err(SemanticSimilarityError::Closure(_))
    ));
    assert!(matches!(
        engine.nearest_neighbors(&id("Unknown"), 3),
        Err(SemanticSimilarityError::Closure(_))
    ));
}

#[test]
fn sse_008_ir_serialization() {
    let engine = similarity_engine();
    let result = engine.similarity(&id("Dog"), &id("Wolf")).unwrap();
    let result_ir = SimilarityResultIrNode::from(&result);
    let report = engine.nearest_neighbors(&id("Dog"), 3).unwrap();
    let report_ir = SimilarityReportIrNode::from(&report);

    assert_eq!(result_ir.node_type, SIMILARITY_RESULT_NODE);
    assert_eq!(report_ir.node_type, SIMILARITY_REPORT_NODE);
    assert_eq!(report_ir.version, SEMANTIC_SIMILARITY_VERSION);
    assert_eq!(report_ir.neighbors.len(), 3);

    let value = serde_json::to_value(&result_ir).unwrap();
    assert_eq!(value["left"], "Dog");
    assert_eq!(value["right"], "Wolf");
    assert_eq!(value["node_type"], "SimilarityResult");
}

#[test]
fn sse_009_json_round_trip() {
    let engine = similarity_engine();
    let result = engine.similarity(&id("Dog"), &id("Wolf")).unwrap();
    let report = engine.nearest_neighbors(&id("Dog"), 3).unwrap();

    let restored_result: SimilarityResult =
        serde_json::from_str(&serde_json::to_string(&result).unwrap()).unwrap();
    let restored_report: SimilarityReport =
        serde_json::from_str(&report.to_json_pretty().unwrap()).unwrap();

    assert_eq!(restored_result, result);
    assert_eq!(restored_report, report);

    let ir = SimilarityReportIrNode::from(&report);
    let restored_ir: SimilarityReportIrNode =
        serde_json::from_str(&serde_json::to_string(&ir).unwrap()).unwrap();
    assert_eq!(restored_ir, ir);
}

#[test]
fn sse_010_determinism() {
    let engine = similarity_engine();
    let expected = engine.nearest_neighbors(&id("Dog"), 5).unwrap();
    let expected_json = expected.to_json_pretty().unwrap();

    for _ in 0..100 {
        let actual = engine.nearest_neighbors(&id("Dog"), 5).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual.to_json_pretty().unwrap(), expected_json);
    }
}

#[test]
fn equal_similarity_scores_are_ordered_by_semantic_type_id() {
    let mut types = SemanticTypeRegistry::new();
    types.register_type(SemanticType::root("Entity")).unwrap();
    types
        .register_type(SemanticType::child("Root", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Beta", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Alpha", "Entity"))
        .unwrap();
    let engine = SemanticSimilarityEngine::new(SemanticClosureEngine::new(
        types,
        SemanticConstraintRegistry::new(),
    ));

    let report = engine.nearest_neighbors(&id("Root"), 3).unwrap();

    assert_eq!(
        report
            .neighbors
            .iter()
            .map(|result| result.right.as_str())
            .collect::<Vec<_>>(),
        vec!["Entity", "Alpha", "Beta"]
    );
}

#[test]
fn disconnected_type_trees_return_no_common_ancestor() {
    let types = SemanticTypeRegistry::from_types([
        SemanticType::root("LeftRoot"),
        SemanticType::root("RightRoot"),
    ])
    .unwrap();
    let engine = SemanticSimilarityEngine::new(SemanticClosureEngine::new(
        types,
        SemanticConstraintRegistry::new(),
    ));

    assert_eq!(
        engine.distance(&id("LeftRoot"), &id("RightRoot")),
        Err(SemanticSimilarityError::NoCommonAncestor {
            left: "LeftRoot".to_string(),
            right: "RightRoot".to_string(),
        })
    );
}
