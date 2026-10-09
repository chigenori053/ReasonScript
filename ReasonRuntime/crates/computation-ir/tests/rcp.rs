use reasonscript_computation_ir::reason_structure::{ReasonStructure, ReasonUnitMode};
use reasonscript_native_reasonunit_runtime::rcp::*;
use serde_json::json;

#[test]
fn native_runtime_semantics_transfer_losslessly_between_domains() {
    let mut runtime = ReasonStructure::new(ReasonUnitMode::RusWithState);
    runtime.record(
        "UNKNOWN_DETECTED",
        &json!("question"),
        &json!({"knowledge":"missing"}),
    );
    runtime.record("TERMINATION_INFERRED", &json!("answer"), &json!(true));
    let original = runtime.trace();
    let payload = runtime.structural_payload().unwrap();
    assert!(payload
        .records
        .iter()
        .any(|record| record.reference.kind == ReferenceKind::RUS));
    assert!(!payload
        .records
        .iter()
        .any(|record| record.reference.kind == ReferenceKind::RUO));
    let message = RCPMessage {
        schema: SCHEMA.into(),
        protocol_version: VERSION.into(),
        message_id: "message:runtime".into(),
        source: "dsn:first".into(),
        destination: "dsn:second".into(),
        kind: RCPKind::Request,
        correlation_id: "trace:runtime".into(),
        causation_id: None,
        trace: vec![],
        payload,
    };
    let mut dispatcher = RCPDispatcher::new(RCPLimits {
        messages: 2,
        requests: 1,
        hops: 2,
        bytes: 100_000,
    });
    dispatcher
        .router
        .register("dsn:first".into(), "core:first".into())
        .unwrap();
    dispatcher
        .router
        .register("dsn:second".into(), "core:second".into())
        .unwrap();
    dispatcher.dispatch(&message.encode().unwrap()).unwrap();
    let receipt = dispatcher.receive("dsn:second").unwrap().remove(0);
    for (section, kind) in [
        ("reason_units", ReferenceKind::RU),
        ("execution_states", ReferenceKind::ExecutionState),
        ("reason_structures", ReferenceKind::RUS),
        ("spatial_objects", ReferenceKind::RUO),
        ("execution_bindings", ReferenceKind::ExecutionBinding),
        ("evidence", ReferenceKind::Evidence),
        ("execution_relations", ReferenceKind::ExecutionRelation),
        ("relations", ReferenceKind::Relation),
    ] {
        let transferred: Vec<_> = receipt
            .payload
            .records
            .iter()
            .filter(|r| r.reference.kind == kind)
            .map(|r| r.value.clone())
            .collect();
        assert_eq!(json!(transferred), original[section]);
    }
}
