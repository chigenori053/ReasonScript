use reasonscript_hybrid_runtime::{
    ConsistencyStatus, ConstraintKind, ConstraintPolarity, ContradictionKind,
    SemanticClosureEngine, SemanticConstraint, SemanticConstraintRegistry,
    SemanticContradictionEngine, SemanticContradictionIrNode, SemanticType, SemanticTypeId,
    SemanticTypeRegistry, SemanticValidationReport, SemanticValidationReportIrNode,
    SEMANTIC_CONTRADICTION_NODE, SEMANTIC_CONTRADICTION_VERSION, SEMANTIC_VALIDATION_REPORT_NODE,
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

fn engine_with(
    constraints: impl IntoIterator<Item = SemanticConstraint>,
) -> SemanticContradictionEngine {
    let types = penguin_types();
    let constraints = SemanticConstraintRegistry::from_constraints(&types, constraints).unwrap();
    SemanticContradictionEngine::new(SemanticClosureEngine::new(types, constraints))
}

fn contradictory_penguin_engine() -> SemanticContradictionEngine {
    engine_with([
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
        constraint(
            "animal-alive",
            "Animal",
            ConstraintKind::Property,
            ConstraintPolarity::Positive,
            "alive",
        ),
    ])
}

#[test]
fn scd_001_positive_only_is_consistent() {
    let engine = engine_with([constraint(
        "animal-alive",
        "Animal",
        ConstraintKind::Property,
        ConstraintPolarity::Positive,
        "alive",
    )]);

    let report = engine.validate(&id("Penguin")).unwrap();

    assert_eq!(report.status, ConsistencyStatus::Consistent);
    assert!(report.contradictions.is_empty());
}

#[test]
fn scd_002_negative_only_is_consistent() {
    let engine = engine_with([constraint(
        "bird-cannot-fly",
        "Bird",
        ConstraintKind::Capability,
        ConstraintPolarity::Negative,
        "fly",
    )]);

    let report = engine.validate(&id("Penguin")).unwrap();

    assert_eq!(report.status, ConsistencyStatus::Consistent);
    assert!(report.contradictions.is_empty());
}

#[test]
fn scd_003_simple_contradiction() {
    let report = contradictory_penguin_engine()
        .validate(&id("Penguin"))
        .unwrap();

    assert_eq!(report.status, ConsistencyStatus::Contradictory);
    assert_eq!(report.contradictions.len(), 1);
    assert_eq!(report.contradictions[0].predicate, "fly");
    assert_eq!(
        report.contradictions[0].kind,
        ContradictionKind::PolarityConflict
    );
    assert_eq!(report.contradictions[0].positive_constraints.len(), 1);
    assert_eq!(report.contradictions[0].negative_constraints.len(), 1);
}

#[test]
fn scd_004_multiple_contradictions() {
    let engine = engine_with([
        constraint(
            "penguin-cannot-fly",
            "Penguin",
            ConstraintKind::Capability,
            ConstraintPolarity::Negative,
            "fly",
        ),
        constraint(
            "penguin-not-alive",
            "Penguin",
            ConstraintKind::Property,
            ConstraintPolarity::Negative,
            "alive",
        ),
        constraint(
            "bird-can-fly",
            "Bird",
            ConstraintKind::Capability,
            ConstraintPolarity::Positive,
            "fly",
        ),
        constraint(
            "animal-alive",
            "Animal",
            ConstraintKind::Property,
            ConstraintPolarity::Positive,
            "alive",
        ),
    ]);

    let report = engine.validate(&id("Penguin")).unwrap();

    assert_eq!(
        report
            .contradictions
            .iter()
            .map(|contradiction| contradiction.predicate.as_str())
            .collect::<Vec<_>>(),
        vec!["fly", "alive"]
    );
}

#[test]
fn scd_005_closure_validation_returns_report() {
    let report = contradictory_penguin_engine()
        .validate(&id("Penguin"))
        .unwrap();

    assert_eq!(report.root_type, id("Penguin"));
    assert_eq!(report.status, ConsistencyStatus::Contradictory);
    assert_eq!(report.contradictions[0].predicate, "fly");
}

#[test]
fn scd_006_is_consistent_returns_false() {
    let engine = contradictory_penguin_engine();
    let closure = engine
        .closure_engine()
        .build_closure(&id("Penguin"))
        .unwrap();

    assert!(!engine.is_consistent(&closure));
}

#[test]
fn scd_007_find_contradictions_returns_fly() {
    let engine = contradictory_penguin_engine();
    let closure = engine
        .closure_engine()
        .build_closure(&id("Penguin"))
        .unwrap();

    let contradictions = engine.find_contradictions(&closure);

    assert_eq!(contradictions.len(), 1);
    assert_eq!(contradictions[0].predicate, "fly");
}

#[test]
fn scd_008_ir_serialization() {
    let report = contradictory_penguin_engine()
        .validate(&id("Penguin"))
        .unwrap();
    let ir = SemanticValidationReportIrNode::from(&report);
    let value = serde_json::to_value(&ir).unwrap();

    assert_eq!(ir.node_type, SEMANTIC_VALIDATION_REPORT_NODE);
    assert_eq!(ir.version, SEMANTIC_CONTRADICTION_VERSION);
    assert_eq!(value["status"], "Contradictory");
    assert_eq!(
        value["contradictions"][0]["node_type"],
        "SemanticContradiction"
    );
    assert_eq!(value["contradictions"][0]["predicate"], "fly");
    assert_eq!(value["contradictions"][0]["kind"], "PolarityConflict");

    let contradiction_ir = SemanticContradictionIrNode::from(&report.contradictions[0]);
    assert_eq!(contradiction_ir.node_type, SEMANTIC_CONTRADICTION_NODE);
}

#[test]
fn scd_009_json_round_trip() {
    let report = contradictory_penguin_engine()
        .validate(&id("Penguin"))
        .unwrap();
    let json = report.to_json_pretty().unwrap();
    let restored: SemanticValidationReport = serde_json::from_str(&json).unwrap();

    assert_eq!(restored, report);

    let ir = SemanticValidationReportIrNode::from(&report);
    let ir_json = serde_json::to_string(&ir).unwrap();
    let restored_ir: SemanticValidationReportIrNode = serde_json::from_str(&ir_json).unwrap();
    assert_eq!(restored_ir, ir);
}

#[test]
fn scd_010_determinism() {
    let engine = contradictory_penguin_engine();
    let expected = engine.validate(&id("Penguin")).unwrap();
    let expected_json = expected.to_json_pretty().unwrap();

    for _ in 0..100 {
        let actual = engine.validate(&id("Penguin")).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual.to_json_pretty().unwrap(), expected_json);
    }
}

#[test]
fn contradiction_detection_groups_by_predicate_across_constraint_kinds() {
    let engine = engine_with([
        constraint(
            "bird-fly-capability",
            "Bird",
            ConstraintKind::Capability,
            ConstraintPolarity::Positive,
            "fly",
        ),
        constraint(
            "penguin-fly-restriction",
            "Penguin",
            ConstraintKind::Restriction,
            ConstraintPolarity::Negative,
            "fly",
        ),
    ]);

    let report = engine.validate(&id("Penguin")).unwrap();

    assert_eq!(report.contradictions.len(), 1);
    assert_eq!(report.contradictions[0].predicate, "fly");
}

#[test]
fn validation_does_not_remove_or_override_constraints() {
    let engine = contradictory_penguin_engine();
    let closure = engine
        .closure_engine()
        .build_closure(&id("Penguin"))
        .unwrap();
    let before = closure.clone();

    let contradictions = engine.find_contradictions(&closure);

    assert_eq!(contradictions.len(), 1);
    assert_eq!(closure, before);
    assert_eq!(closure.constraints.len(), 3);
}

#[test]
fn consistent_report_helper_matches_status() {
    let engine = engine_with([constraint(
        "animal-alive",
        "Animal",
        ConstraintKind::Property,
        ConstraintPolarity::Positive,
        "alive",
    )]);
    let report = engine.validate(&id("Penguin")).unwrap();

    assert!(report.is_consistent());
}
