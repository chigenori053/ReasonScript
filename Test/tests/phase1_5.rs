use reasonunit_phase1_test::{
    DeriveOperator, OperationKind, Payload, ReplayTrace, Runtime, UnitKind, UnitState,
};

#[test]
fn experiment_e_persistence_roundtrip_preserves_complete_unit() {
    let unit = Runtime::create_unit(Payload::Token("apple".to_string()));

    let bytes = Runtime::serialize_unit(&unit);
    let restored = Runtime::deserialize_unit(&bytes).unwrap();

    assert_eq!(restored, unit);
    assert_eq!(restored.id, unit.id);
    assert_eq!(restored.kind, UnitKind::Token);
    assert_eq!(restored.payload, Payload::Token("apple".to_string()));
    assert_eq!(restored.state, UnitState::Created);
    assert_eq!(restored.trace, unit.trace);
    assert_eq!(restored.links, unit.links);
}

#[test]
fn experiment_f_deterministic_replay_reconstructs_same_result_trace_and_dependency() {
    let left = Runtime::create_unit(Payload::Number(2));
    let right = Runtime::create_unit(Payload::Number(3));
    let derived =
        Runtime::derive_unit(&[left.clone(), right.clone()], DeriveOperator::Add).unwrap();
    let trace = ReplayTrace::from_derived(
        vec![left.clone(), right.clone()],
        DeriveOperator::Add,
        &derived,
    );

    let replayed = Runtime::replay(&trace).unwrap();

    assert_eq!(replayed.id, derived.id);
    assert_eq!(replayed.payload, Payload::Number(5));
    assert_eq!(replayed.payload, derived.payload);
    assert_eq!(replayed.state, derived.state);
    assert_eq!(replayed.trace, derived.trace);
    assert_eq!(replayed.links, derived.links);
    assert_eq!(
        replayed.trace.parent_ids,
        vec![left.id.clone(), right.id.clone()]
    );
}

#[test]
fn experiment_g_rollback_cascade_invalidates_downstream_linear_dependency() {
    let a = Runtime::create_unit(Payload::Number(2));
    let three = Runtime::create_unit(Payload::Number(3));
    let four = Runtime::create_unit(Payload::Number(4));

    let mut b = Runtime::derive_unit(&[a.clone(), three], DeriveOperator::Add).unwrap();
    b.state = UnitState::Failed;
    let c = Runtime::derive_unit(&[b.clone(), four], DeriveOperator::Add).unwrap();

    let updated = Runtime::rollback_cascade(&[a.clone(), b.clone(), c.clone()], &b.id);
    let updated_a = &updated[0];
    let updated_b = &updated[1];
    let updated_c = &updated[2];

    assert_eq!(updated_a.state, UnitState::Created);
    assert_eq!(updated_b.state, UnitState::RolledBack);
    assert_eq!(updated_b.trace.operation, OperationKind::Rollback);
    assert_eq!(updated_b.trace.parent_ids, b.trace.parent_ids);
    assert_eq!(updated_c.state, UnitState::Invalidated);
    assert_eq!(updated_c.trace.parent_ids, c.trace.parent_ids);
    assert_eq!(updated_c.links, c.links);
}

#[test]
fn experiment_h_long_chain_stability_keeps_trace_dependency_and_rollback_valid() {
    let mut chain = Vec::new();
    chain.push(Runtime::create_unit(Payload::Number(1)));

    for i in 2..=100 {
        let previous = chain.last().unwrap().clone();
        let increment = Runtime::create_unit(Payload::Number(i));
        let derived =
            Runtime::derive_unit(&[previous.clone(), increment.clone()], DeriveOperator::Add)
                .unwrap();

        assert_eq!(derived.state, UnitState::Derived);
        assert_eq!(derived.trace.operation, OperationKind::Derive);
        assert_eq!(
            derived.trace.parent_ids,
            vec![previous.id.clone(), increment.id.clone()]
        );
        assert_eq!(
            derived.links,
            vec![previous.id.clone(), increment.id.clone()]
        );

        chain.push(derived);
    }

    assert_eq!(chain.len(), 100);
    assert_eq!(chain.last().unwrap().payload, Payload::Number(5050));

    for window in chain.windows(2) {
        let previous = &window[0];
        let current = &window[1];
        assert!(current.trace.parent_ids.contains(&previous.id));
        assert_eq!(current.state, UnitState::Derived);
    }

    let rollback_target = chain[50].id.clone();
    let cascaded = Runtime::rollback_cascade(&chain, &rollback_target);

    assert_eq!(cascaded[50].state, UnitState::RolledBack);
    assert_eq!(cascaded[51].state, UnitState::Invalidated);
    assert_eq!(cascaded[99].state, UnitState::Invalidated);
    assert_eq!(cascaded[49].state, UnitState::Derived);
    assert_eq!(cascaded[99].trace.parent_ids, chain[99].trace.parent_ids);
    assert_eq!(cascaded[99].links, chain[99].links);
}

#[test]
fn phase1_5_state_machine_allows_rollback_to_invalidated() {
    let mut unit = Runtime::create_unit(Payload::Symbol("unstable".to_string()));
    Runtime::transition(&mut unit, UnitState::Active).unwrap();
    Runtime::transition(&mut unit, UnitState::Derived).unwrap();
    Runtime::transition(&mut unit, UnitState::Failed).unwrap();
    Runtime::transition(&mut unit, UnitState::RolledBack).unwrap();
    Runtime::transition(&mut unit, UnitState::Invalidated).unwrap();

    assert_eq!(unit.state, UnitState::Invalidated);
}
