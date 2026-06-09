use reasonunit_phase1_test::{
    DeriveOperator, OperationKind, Payload, Runtime, RuntimeError, TransformRule, UnitKind,
    UnitState,
};

#[test]
fn experiment_a_creates_token_unit() {
    let unit = Runtime::create_unit(Payload::Token("apple".to_string()));

    assert_eq!(unit.kind, UnitKind::Token);
    assert_eq!(unit.payload, Payload::Token("apple".to_string()));
    assert_eq!(unit.state, UnitState::Created);
    assert_eq!(unit.trace.operation, OperationKind::Create);
    assert!(unit.trace.parent_ids.is_empty());
    assert!(unit.links.is_empty());
}

#[test]
fn experiment_b_transforms_token_and_keeps_traceability() {
    let source = Runtime::create_unit(Payload::Token("apple".to_string()));
    let transformed = Runtime::transform_unit(&source, TransformRule::Synonym).unwrap();

    assert_eq!(transformed.kind, UnitKind::Token);
    assert_eq!(transformed.payload, Payload::Token("fruit".to_string()));
    assert_eq!(transformed.state, UnitState::Derived);
    assert_eq!(transformed.trace.operation, OperationKind::Transform);
    assert_eq!(transformed.trace.parent_ids, vec![source.id.clone()]);
    assert_eq!(transformed.links, vec![source.id.clone()]);
}

#[test]
fn experiment_c_derives_numeric_sum_with_dependencies() {
    let left = Runtime::create_unit(Payload::Number(2));
    let right = Runtime::create_unit(Payload::Number(3));
    let derived =
        Runtime::derive_unit(&[left.clone(), right.clone()], DeriveOperator::Add).unwrap();

    assert_eq!(derived.kind, UnitKind::Number);
    assert_eq!(derived.payload, Payload::Number(5));
    assert_eq!(derived.state, UnitState::Derived);
    assert_eq!(derived.trace.operation, OperationKind::Derive);
    assert_eq!(
        derived.trace.parent_ids,
        vec![left.id.clone(), right.id.clone()]
    );
    assert_eq!(derived.links, vec![left.id.clone(), right.id.clone()]);
}

#[test]
fn experiment_d_rolls_back_invalid_result_and_rederives() {
    let left = Runtime::create_unit(Payload::Number(2));
    let right = Runtime::create_unit(Payload::Number(3));

    let mut invalid = Runtime::create_unit(Payload::Number(6));
    invalid.state = UnitState::Failed;
    invalid.links = vec![left.id.clone(), right.id.clone()];
    invalid.trace.parent_ids = vec![left.id.clone(), right.id.clone()];
    invalid.trace.operation = OperationKind::Derive;

    let rolled_back = Runtime::rollback_unit(&invalid);
    assert_eq!(rolled_back.state, UnitState::RolledBack);
    assert_eq!(rolled_back.trace.operation, OperationKind::Rollback);
    assert_eq!(
        rolled_back.trace.parent_ids,
        vec![left.id.clone(), right.id.clone()]
    );
    assert_eq!(rolled_back.links, vec![left.id.clone(), right.id.clone()]);

    let corrected =
        Runtime::derive_unit(&[left.clone(), right.clone()], DeriveOperator::Add).unwrap();
    assert_eq!(corrected.payload, Payload::Number(5));
    assert_eq!(corrected.state, UnitState::Derived);
    assert_eq!(
        corrected.trace.parent_ids,
        vec![left.id.clone(), right.id.clone()]
    );
}

#[test]
fn validates_allowed_state_transitions() {
    let mut unit = Runtime::create_unit(Payload::Symbol("x".to_string()));

    Runtime::transition(&mut unit, UnitState::Active).unwrap();
    Runtime::transition(&mut unit, UnitState::Derived).unwrap();
    Runtime::transition(&mut unit, UnitState::Failed).unwrap();
    Runtime::transition(&mut unit, UnitState::RolledBack).unwrap();
    Runtime::transition(&mut unit, UnitState::Active).unwrap();

    assert_eq!(unit.state, UnitState::Active);
}

#[test]
fn rejects_invalid_state_transitions() {
    let mut converged = Runtime::create_unit(Payload::Symbol("done".to_string()));
    converged.state = UnitState::Converged;

    let result = Runtime::transition(&mut converged, UnitState::Created);
    assert_eq!(
        result,
        Err(RuntimeError::InvalidTransition {
            from: UnitState::Converged,
            to: UnitState::Created,
        })
    );
    assert_eq!(converged.state, UnitState::Converged);

    let mut rolled_back = Runtime::create_unit(Payload::Symbol("rb".to_string()));
    rolled_back.state = UnitState::RolledBack;
    assert!(Runtime::transition(&mut rolled_back, UnitState::Converged).is_err());

    let mut failed = Runtime::create_unit(Payload::Symbol("failed".to_string()));
    failed.state = UnitState::Failed;
    assert!(Runtime::transition(&mut failed, UnitState::Created).is_err());
}
