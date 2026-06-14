use reasonscript_hybrid_runtime::{
    ConstraintKind, ConstraintPolarity, PathSearchResult, PathSearchResultIrNode, SearchKind,
    SearchQuery, SearchResult, SearchResultIrNode, SearchResultItemIrNode, SemanticClosureEngine,
    SemanticConstraint, SemanticConstraintRegistry, SemanticPlanningEngine, SemanticSearchEngine,
    SemanticSearchError, SemanticSimilarityEngine, SemanticTransformationEngine, SemanticType,
    SemanticTypeError, SemanticTypeId, SemanticTypeRegistry, PATH_SEARCH_RESULT_NODE,
    SEARCH_RESULT_ITEM_NODE, SEARCH_RESULT_NODE,
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

fn search_engine() -> SemanticSearchEngine {
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
    types
        .register_type(SemanticType::child("Wolf", "LivingThing"))
        .unwrap();
    types
        .register_type(SemanticType::child("Fox", "LivingThing"))
        .unwrap();
    types
        .register_type(SemanticType::child("Vehicle", "Entity"))
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
            constraint("wolf-alive", "Wolf", "alive"),
            constraint("wolf-move", "Wolf", "move"),
            constraint("wolf-eat", "Wolf", "eat"),
            constraint("wolf-domesticated", "Wolf", "domesticated"),
            constraint("wolf-social", "Wolf", "social"),
            constraint("wolf-warm", "Wolf", "warm"),
            constraint("fox-alive", "Fox", "alive"),
            constraint("fox-move", "Fox", "move"),
            constraint("fox-eat", "Fox", "eat"),
            constraint("fox-hunt", "Fox", "hunt"),
            constraint("fox-domesticated", "Fox", "domesticated"),
            constraint("fox-social", "Fox", "social"),
            constraint("fox-warm", "Fox", "warm"),
            constraint("cat-domesticated", "Cat", "domesticated"),
            constraint("cat-eat", "Cat", "eat"),
            constraint("cat-purr", "Cat", "purr"),
            constraint("cat-warm", "Cat", "warm"),
            constraint("bird-fly", "Bird", "fly"),
        ],
    )
    .unwrap();
    let similarity_engine =
        SemanticSimilarityEngine::new(SemanticClosureEngine::new(types.clone(), constraints));
    let transformation_engine = SemanticTransformationEngine::new(types.clone());
    let planning_engine =
        SemanticPlanningEngine::new(SemanticTransformationEngine::new(types.clone()));

    SemanticSearchEngine::new(
        types,
        similarity_engine,
        transformation_engine,
        planning_engine,
    )
}

fn item_ids(result: &SearchResult) -> Vec<&str> {
    result
        .items
        .iter()
        .map(|item| item.type_id.as_str())
        .collect()
}

#[test]
fn ssea_001_ancestor_search() {
    let result = search_engine().ancestors(&id("Dog")).unwrap();

    assert_eq!(item_ids(&result), vec!["Animal", "LivingThing", "Entity"]);
    assert!(result.items.iter().all(|item| item.score == 1.0));
}

#[test]
fn ssea_002_descendant_search() {
    let result = search_engine().descendants(&id("Animal")).unwrap();

    assert_eq!(item_ids(&result), vec!["Dog", "Cat", "Bird"]);
}

#[test]
fn ssea_003_similarity_search() {
    let result = search_engine().similar(&id("Dog"), 3).unwrap();

    assert_eq!(item_ids(&result), vec!["Wolf", "Fox", "Cat"]);
    assert!(result
        .items
        .windows(2)
        .all(|items| items[0].score >= items[1].score));
}

#[test]
fn ssea_004_limit() {
    let result = search_engine()
        .search(SearchQuery {
            root: id("Dog"),
            kind: SearchKind::Similarity,
            limit: Some(2),
        })
        .unwrap();

    assert_eq!(result.items.len(), 2);
    assert_eq!(item_ids(&result), vec!["Wolf", "Fox"]);
}

#[test]
fn ssea_005_reachability() {
    let result = search_engine().reachable(&id("Dog")).unwrap();

    assert_eq!(item_ids(&result), vec!["Animal", "LivingThing", "Entity"]);
}

#[test]
fn ssea_006_path_search() {
    let result = search_engine().path(&id("Dog"), &id("Entity")).unwrap();

    assert_eq!(
        result.path.nodes,
        vec![id("Dog"), id("Animal"), id("LivingThing"), id("Entity")]
    );
    assert_eq!(result.distance, 3);
}

#[test]
fn ssea_007_unknown_type() {
    assert_eq!(
        search_engine().ancestors(&id("Unknown")),
        Err(SemanticSearchError::TypeHierarchy(
            SemanticTypeError::TypeNotFound("Unknown".to_string())
        ))
    );
    assert!(matches!(
        search_engine().similar(&id("Unknown"), 3),
        Err(SemanticSearchError::Similarity(_))
    ));
    assert!(matches!(
        search_engine().path(&id("Unknown"), &id("Entity")),
        Err(SemanticSearchError::Planning(_))
    ));
}

#[test]
fn ssea_008_ir_serialization() {
    let result = search_engine().similar(&id("Dog"), 2).unwrap();
    let item_ir = SearchResultItemIrNode::from(&result.items[0]);
    let result_ir = SearchResultIrNode::from(&result);
    let path = search_engine().path(&id("Dog"), &id("Entity")).unwrap();
    let path_ir = PathSearchResultIrNode::from(&path);

    assert_eq!(item_ir.node_type, SEARCH_RESULT_ITEM_NODE);
    assert_eq!(result_ir.node_type, SEARCH_RESULT_NODE);
    assert_eq!(result_ir.kind, SearchKind::Similarity);
    assert_eq!(path_ir.node_type, PATH_SEARCH_RESULT_NODE);
    assert_eq!(path_ir.distance, 3);
}

#[test]
fn ssea_009_json_roundtrip() {
    let result = search_engine().similar(&id("Dog"), 3).unwrap();
    let path = search_engine().path(&id("Dog"), &id("Entity")).unwrap();

    let restored_result: SearchResult =
        serde_json::from_str(&result.to_json_pretty().unwrap()).unwrap();
    let restored_path: PathSearchResult =
        serde_json::from_str(&path.to_json_pretty().unwrap()).unwrap();
    assert_eq!(restored_result.query, result.query);
    assert_eq!(restored_result.items.len(), result.items.len());
    for (restored, original) in restored_result.items.iter().zip(&result.items) {
        assert_eq!(restored.type_id, original.type_id);
        assert!((restored.score - original.score).abs() < f64::EPSILON);
    }
    assert_eq!(restored_path, path);

    let ir = SearchResultIrNode::from(&result);
    let restored_ir: SearchResultIrNode =
        serde_json::from_str(&serde_json::to_string(&ir).unwrap()).unwrap();
    assert_eq!(restored_ir.node_type, ir.node_type);
    assert_eq!(restored_ir.kind, ir.kind);
    assert_eq!(restored_ir.items.len(), ir.items.len());
    for (restored, original) in restored_ir.items.iter().zip(&ir.items) {
        assert_eq!(restored.node_type, original.node_type);
        assert_eq!(restored.type_id, original.type_id);
        assert!((restored.score - original.score).abs() < f64::EPSILON);
    }
}

#[test]
fn ssea_010_determinism() {
    let engine = search_engine();
    let expected_similarity = engine.similar(&id("Dog"), 5).unwrap();
    let expected_reachable = engine.reachable(&id("Animal")).unwrap();
    let expected_path = engine.path(&id("Dog"), &id("Entity")).unwrap();

    for _ in 0..100 {
        assert_eq!(engine.similar(&id("Dog"), 5).unwrap(), expected_similarity);
        assert_eq!(engine.reachable(&id("Animal")).unwrap(), expected_reachable);
        assert_eq!(
            engine.path(&id("Dog"), &id("Entity")).unwrap(),
            expected_path
        );
    }
}

#[test]
fn generic_search_applies_limits_to_non_similarity_results() {
    let result = search_engine()
        .search(SearchQuery {
            root: id("Animal"),
            kind: SearchKind::Descendant,
            limit: Some(2),
        })
        .unwrap();

    assert_eq!(item_ids(&result), vec!["Dog", "Cat"]);
}

#[test]
fn path_kind_requires_the_dedicated_path_api() {
    assert_eq!(
        search_engine().search(SearchQuery {
            root: id("Dog"),
            kind: SearchKind::Path,
            limit: None,
        }),
        Err(SemanticSearchError::PathQueryRequiresTarget)
    );
}

#[test]
fn reachability_combines_ancestors_and_descendants_without_root() {
    let result = search_engine().reachable(&id("Animal")).unwrap();

    assert_eq!(
        item_ids(&result),
        vec!["LivingThing", "Entity", "Dog", "Cat", "Bird",]
    );
    assert!(!item_ids(&result).contains(&"Animal"));
}
