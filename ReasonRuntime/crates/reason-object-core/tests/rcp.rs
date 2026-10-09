use reasonscript_native_reasonunit_runtime::rcp::*;
use serde_json::{json, Value};
fn reference(kind: ReferenceKind, id: &str) -> RCPReference {
    RCPReference {
        kind,
        id: id.into(),
    }
}
fn payload() -> RCPPayload {
    RCPPayload::from_runtime_trace(&json!({
        "schema":reasonscript_native_reasonunit_runtime::structure::TRACE_SCHEMA,
        "reason_units":[{"id":"ru:1","kind":"query","content":{"question":"missing knowledge"}}],
        "reason_structures":[],"spatial_objects":[],"relations":[],
        "execution_states":[{"id":"state:1","revision":0,"changed_fields":[],"goal_status":"ACTIVE","semantic_subject":"question"}],
        "execution_bindings":[{"id":"binding:1","reason_unit_ref":"ru:1","execution_state_ref":"state:1","evidence_refs":["evidence:1"],"execution_relation_refs":["execution-relation:1"],"status":"ACTIVE","lifecycle":["CREATED","ACTIVE"]}],
        "evidence":[{"id":"evidence:1","source_ru":"ru:1","value":{"score":0.25}}],
        "execution_relations":[{"id":"execution-relation:1","kind":"PRODUCES","source_ref":"ru:1","target_ref":"evidence:1"}]
    })).unwrap()
}
fn message() -> RCPMessage {
    RCPMessage {
        schema: SCHEMA.into(),
        protocol_version: VERSION.into(),
        message_id: "message:1".into(),
        source: "dsn:a".into(),
        destination: "dsn:b".into(),
        kind: RCPKind::Request,
        correlation_id: "conversation:1".into(),
        causation_id: None,
        trace: vec![],
        payload: payload(),
    }
}
fn dispatcher(messages: usize, requests: usize) -> RCPDispatcher {
    let mut d = RCPDispatcher::new(RCPLimits {
        messages,
        requests,
        hops: 8,
        bytes: 100_000,
    });
    d.router.register("dsn:a".into(), "core:a".into()).unwrap();
    d.router.register("dsn:b".into(), "core:b".into()).unwrap();
    d.router.register("dsn:c".into(), "core:c".into()).unwrap();
    d
}
fn unknown() -> UnknownUnit {
    UnknownUnit {
        id: "unknown:1".into(),
        origins: vec![reference(ReferenceKind::RU, "ru:1")],
        cause: UnknownCause::MissingEvidence,
        grounds: vec![],
        dependencies: vec![],
        history: vec![UnknownRevision {
            state: UnknownState::Open,
            evidence: vec![],
            candidate: None,
        }],
    }
}
struct Policy;
impl CandidateValidator for Policy {
    fn validate(&self, _: &UnknownUnit, value: &Value) -> RCPResult<()> {
        if value == "answer" {
            Ok(())
        } else {
            Err("domain rejected candidate".into())
        }
    }
}
#[test]
fn rcp_t01_message_roundtrip() {
    let m = message();
    assert_eq!(
        RCPMessage::decode(&m.encode().unwrap(), 100_000).unwrap(),
        m
    );
}
#[test]
fn rcp_t02_semantic_transfer() {
    let mut p = payload();
    p.records.push(RCPRecord {
        reference: reference(ReferenceKind::Knowledge, "knowledge:1"),
        value: json!({"id":"knowledge:1","facts":[1,2,3]}),
        references: vec![],
    });
    p.records[0]
        .references
        .push(reference(ReferenceKind::Knowledge, "knowledge:1"));
    let mut m = message();
    m.payload = p.clone();
    let mut d = dispatcher(8, 8);
    d.dispatch(&m.encode().unwrap()).unwrap();
    assert_eq!(d.receive("dsn:b").unwrap()[0].payload, p);
}
#[test]
fn rcp_t03_unknown_identity_origin() {
    let u = unknown();
    let mut p = payload();
    p.unknowns.push(u.clone());
    p.validate().unwrap();
    assert_eq!(u.origins[0].id, "ru:1");
    assert_ne!(u.id, u.origins[0].id);
    let mut alias = u.clone();
    alias.id = alias.origins[0].id.clone();
    assert!(alias.validate().is_err());
}
#[test]
fn rcp_t04_journal_transitions() {
    let mut registry = UnknownRegistry::default();
    let mut u = unknown();
    registry.commit(u.clone(), &payload(), &Policy).unwrap();
    let mut invalid = u.clone();
    invalid.history.push(UnknownRevision {
        state: UnknownState::Resolved,
        evidence: vec![],
        candidate: None,
    });
    assert!(registry.commit(invalid, &payload(), &Policy).is_err());
    for state in [
        UnknownState::InProgress,
        UnknownState::Candidate,
        UnknownState::Resolved,
    ] {
        let candidate = if state == UnknownState::InProgress {
            None
        } else {
            Some(json!("answer"))
        };
        u.history.push(UnknownRevision {
            state,
            evidence: vec![reference(ReferenceKind::Evidence, "evidence:1")],
            candidate,
        });
        registry.commit(u.clone(), &payload(), &Policy).unwrap();
    }
    assert_eq!(registry.get("unknown:1").unwrap().history.len(), 4);
    let mut tampered = u.clone();
    tampered.origins[0].id = "ru:other".into();
    assert!(registry.commit(tampered, &payload(), &Policy).is_err());
}
#[test]
fn rcp_t05_request_result() {
    let mut d = dispatcher(8, 8);
    d.dispatch(&message().encode().unwrap()).unwrap();
    let received = d.receive("dsn:b").unwrap().remove(0);
    let mut reply = message();
    reply.kind = RCPKind::Result;
    reply.message_id = "message:2".into();
    reply.source = "dsn:b".into();
    reply.destination = "dsn:a".into();
    reply.causation_id = Some(received.message_id);
    reply.trace = received.trace;
    d.dispatch(&reply.encode().unwrap()).unwrap();
    assert_eq!(d.receive("dsn:a").unwrap()[0].kind, RCPKind::Result);
}
#[test]
fn rcp_t06_duplicate_cycle_limits() {
    let mut d = dispatcher(1, 1);
    let bytes = message().encode().unwrap();
    d.dispatch(&bytes).unwrap();
    assert!(d.dispatch(&bytes).is_err());
    let mut m = message();
    m.message_id = "message:2".into();
    assert!(d.dispatch(&m.encode().unwrap()).is_err());
    m.trace = vec!["dsn:b".into(), "dsn:a".into()];
    assert!(m.encode().is_err());
    let mut d = dispatcher(8, 0);
    assert!(d.dispatch(&bytes).is_err());
    assert!(d.receive("dsn:b").unwrap().is_empty());
}
#[test]
fn rcp_t07_determinism() {
    let run = || {
        let mut d = dispatcher(8, 8);
        d.dispatch(&message().encode().unwrap()).unwrap();
        serde_json::to_vec(&d.receive("dsn:b").unwrap()).unwrap()
    };
    assert_eq!(run(), run());
    assert_eq!(message().encode().unwrap(), message().encode().unwrap());
}
#[test]
fn rcp_t08_reject_invalid() {
    let m = message();
    assert!(RCPMessage::decode(&m.encode().unwrap(), 1).is_err());
    assert!(RCPMessage::decode(b"{}", 1024).is_err());
    let mut m = message();
    m.protocol_version = "0.3".into();
    assert!(m.encode().is_err());
    let mut m = message();
    m.payload.records.pop();
    assert!(m.encode().is_err());
    let mut m = message();
    m.payload.records[0].reference.id = "ru:other".into();
    assert!(m.encode().is_err());
    let mut m = message();
    m.payload
        .records
        .iter_mut()
        .find(|r| r.reference.kind == ReferenceKind::ExecutionBinding)
        .unwrap()
        .references[0]
        .kind = ReferenceKind::Knowledge;
    assert!(m.encode().is_err());
    let mut p = payload();
    let mut u = unknown();
    u.dependencies.push(u.id.clone());
    p.unknowns.push(u);
    assert!(p.validate().is_err());
    let mut value = serde_json::to_value(message()).unwrap();
    value["unexpected"] = json!(true);
    assert!(RCPMessage::decode(&serde_json::to_vec(&value).unwrap(), 100_000).is_err());
}
#[test]
fn rcp_t09_domain_dsn() {
    let mut d = dispatcher(8, 8);
    assert_eq!(d.router.resolve("dsn:b").unwrap(), "core:b");
    assert!(d
        .router
        .register("dsn:b".into(), "core:other".into())
        .is_err());
    let mut m = message();
    m.destination = "dsn:missing".into();
    assert!(d.dispatch(&m.encode().unwrap()).is_err());
    d.dispatch(&message().encode().unwrap()).unwrap();
    let request = d.receive("dsn:b").unwrap().remove(0);
    let mut forward = message();
    forward.message_id = "message:2".into();
    forward.source = "dsn:b".into();
    forward.destination = "dsn:c".into();
    forward.causation_id = Some(request.message_id);
    forward.trace = request.trace;
    d.dispatch(&forward.encode().unwrap()).unwrap();
    assert_eq!(
        d.receive("dsn:c").unwrap()[0].trace,
        vec!["dsn:a", "dsn:b", "dsn:c"]
    );
}

#[test]
fn native_ruo_roundtrip_and_reference_rejection() {
    use reasonscript_native_reasonunit_runtime::NativeReasonUnitObject;
    let object=NativeReasonUnitObject::from_logical(json!({"object_identity":{"entity_id":"ruo:object:1"},"current_revision":"ruo:revision:1","root_units":["ruo:unit:1"],"units":[{"entity_id":"ruo:unit:1"}],"revisions":[{"revision_id":"ruo:revision:1"}],"states":[],"payloads":[],"evidence_registry":[],"relations":[],"constraints":[],"projection_descriptors":[],"extension_registry":[],"metadata":{"extension":[3,1,2]}})).unwrap();
    let payload = RCPPayload::from_native_object(&object).unwrap();
    let restored = payload.native_object("ruo:object:1").unwrap();
    assert_eq!(restored.logical, object.logical);
    assert_eq!(restored.logical_digest, object.logical_digest);
    let mut broken = payload.clone();
    broken.records[0].value["native_logical"]["units"][0]["evidence_refs"] =
        json!(["ruo:evidence:missing"]);
    assert!(broken.validate().is_err());
}

#[test]
fn rejected_candidates_and_missing_context_are_atomic() {
    let mut registry = UnknownRegistry::default();
    let mut u = unknown();
    registry.commit(u.clone(), &payload(), &Policy).unwrap();
    u.history.push(UnknownRevision {
        state: UnknownState::InProgress,
        evidence: vec![],
        candidate: None,
    });
    registry.commit(u.clone(), &payload(), &Policy).unwrap();
    u.history.push(UnknownRevision {
        state: UnknownState::Candidate,
        evidence: vec![reference(ReferenceKind::Evidence, "evidence:1")],
        candidate: Some(json!("wrong")),
    });
    assert!(registry.commit(u.clone(), &payload(), &Policy).is_err());
    assert_eq!(registry.get(&u.id).unwrap().history.len(), 2);
    u.history[2].candidate = Some(json!("answer"));
    u.history[2].evidence[0].id = "evidence:missing".into();
    assert!(registry.commit(u, &payload(), &Policy).is_err());
}

#[test]
fn canonical_native_fixture_transfer() {
    use reasonscript_native_reasonunit_runtime::load_ruo;
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../artifacts/reasonunit_file/ruo_f1/fixtures/complete.ruo");
    let object = load_ruo(&path).unwrap();
    let payload = RCPPayload::from_native_object(&object).unwrap();
    let restored = payload.native_object(object.object_id.as_str()).unwrap();
    assert_eq!(restored.logical, object.logical);
}

#[test]
fn unknown_registry_accepts_each_structural_origin() {
    let a = reference(ReferenceKind::RU, "ru:a");
    let b = reference(ReferenceKind::RU, "ru:b");
    let s = reference(ReferenceKind::RUS, "rus:structure");
    let o = reference(ReferenceKind::RUO, "ruo:spatial");
    let context = RCPPayload {
        records: vec![
            RCPRecord {
                reference: a.clone(),
                value: json!({"id":a.id,"kind":"proposition","content":"a"}),
                references: vec![],
            },
            RCPRecord {
                reference: b.clone(),
                value: json!({"id":b.id,"kind":"condition","content":"b"}),
                references: vec![],
            },
            RCPRecord {
                reference: s.clone(),
                value: json!({"id":s.id,"unit_refs":[a.id,b.id],"relation_refs":[]}),
                references: vec![a.clone(), b.clone()],
            },
            RCPRecord {
                reference: o.clone(),
                value: json!({"id":o.id,"space":"abstract","coordinate_frame":"frame:test","coordinate_unit":"unit","unit_refs":[a.id,b.id],"structure_refs":[s.id],"relation_refs":[],"placements":[{"target":a,"position":[0,0,0],"direction":null},{"target":b,"position":[1,0,0],"direction":null},{"target":s,"position":[0,1,0],"direction":null}]}),
                references: vec![a.clone(), b.clone(), s.clone()],
            },
        ],
        unknowns: vec![],
    };
    context.validate().unwrap();
    let mut registry = UnknownRegistry::default();
    for (i, origin) in [a, s, o].into_iter().enumerate() {
        let mut unit = unknown();
        unit.id = format!("unknown:structural:{i}");
        unit.origins = vec![origin];
        registry.commit(unit.clone(), &context, &Policy).unwrap();
        assert_eq!(registry.get(&unit.id), Some(&unit));
    }
}

#[test]
fn runtime_adapter_rejects_state_reference_to_evidence() {
    let mut trace = serde_json::json!({"schema":reasonscript_native_reasonunit_runtime::structure::TRACE_SCHEMA,"reason_units":[{"id":"ru:1","kind":"query","content":"question"}],"reason_structures":[],"spatial_objects":[],"relations":[],"execution_states":[],"execution_bindings":[{"id":"binding:1","reason_unit_ref":"ru:1","execution_state_ref":"evidence:1","evidence_refs":[],"execution_relation_refs":[],"status":"ACTIVE","lifecycle":[]}],"evidence":[{"id":"evidence:1"}],"execution_relations":[]});
    assert!(RCPPayload::from_runtime_trace(&trace).is_err());
    trace["execution_bindings"] = serde_json::json!([]);
    trace["mode"] = serde_json::json!("rus_with_state");
    assert!(RCPPayload::from_runtime_trace(&trace).is_ok());
    for mode in ["ru_rus", "ru_rus_ruo"] {
        trace["mode"] = serde_json::json!(mode);
        assert!(RCPPayload::from_runtime_trace(&trace).is_err());
    }
    trace["mode"] = serde_json::json!("rus_with_state");
    trace["reason_unit_states"] = serde_json::json!([]);
    assert!(RCPPayload::from_runtime_trace(&trace).is_err());
    trace.as_object_mut().unwrap().remove("reason_unit_states");
    trace["schema"] = serde_json::json!("old-runtime");
    assert!(RCPPayload::from_runtime_trace(&trace).is_err());
}
