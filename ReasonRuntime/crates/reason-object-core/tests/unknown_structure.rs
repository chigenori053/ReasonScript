use reasonscript_native_reasonunit_runtime::rcp::*;
use reasonscript_native_reasonunit_runtime::unknown_structure::*;
use serde_json::{json, Value};

fn r(kind: ReferenceKind, id: &str) -> RCPReference {
    RCPReference {
        kind,
        id: id.into(),
    }
}
fn record(kind: ReferenceKind, value: Value, references: Vec<RCPReference>) -> RCPRecord {
    RCPRecord {
        reference: r(kind, value["id"].as_str().unwrap()),
        value,
        references,
    }
}
fn unit(id: &str, origin: RCPReference, dependencies: &[&str]) -> UnknownReasonUnit {
    UnknownUnit {
        id: id.into(),
        origins: vec![origin],
        cause: UnknownCause::MissingKnowledge,
        grounds: vec![r(ReferenceKind::Knowledge, "knowledge:1")],
        dependencies: dependencies.iter().map(|s| s.to_string()).collect(),
        history: vec![UnknownRevision {
            state: UnknownState::Open,
            evidence: vec![],
            candidate: None,
        }],
    }
}
fn graph() -> UnknownReasonUnitStructure {
    UnknownReasonUnitStructure {
        id: "urus:1".into(),
        uru_refs: vec!["uru:c".into(), "uru:a".into(), "uru:b".into()],
        relation_refs: vec![
            "unknown-relation:ba".into(),
            "unknown-relation:cb".into(),
            "unknown-relation:cause".into(),
            "unknown-relation:block".into(),
            "unknown-relation:related".into(),
            "unknown-relation:conflict".into(),
        ],
    }
}
fn payload() -> RCPPayload {
    let mut records = vec![
        record(
            ReferenceKind::RU,
            json!({"id":"ru:0","kind":"proposition","content":{"known":[1,2]}}),
            vec![],
        ),
        record(
            ReferenceKind::RU,
            json!({"id":"ru:1","kind":"condition","content":"incomplete"}),
            vec![],
        ),
        record(
            ReferenceKind::RUS,
            json!({"id":"rus:0","unit_refs":["ru:0","ru:1"],"relation_refs":[]}),
            vec![r(ReferenceKind::RU, "ru:0"), r(ReferenceKind::RU, "ru:1")],
        ),
        record(
            ReferenceKind::RUO,
            json!({"id":"ruo:0","space":"abstract","coordinate_frame":"frame","coordinate_unit":"unit","unit_refs":["ru:0"],"structure_refs":[],"relation_refs":[],"placements":[{"target":{"kind":"RU","id":"ru:0"},"position":[0.,0.,0.],"direction":null}]}),
            vec![r(ReferenceKind::RU, "ru:0")],
        ),
        record(
            ReferenceKind::Evidence,
            json!({"id":"evidence:1","value":"observation"}),
            vec![],
        ),
        record(
            ReferenceKind::Knowledge,
            json!({"id":"knowledge:1","value":{"fact":true}}),
            vec![],
        ),
    ];
    for (id, kind, source, target) in [
        (
            "ba",
            UnknownRelationKind::DependsOn,
            "uru:b",
            r(ReferenceKind::URU, "uru:a"),
        ),
        (
            "cb",
            UnknownRelationKind::DependsOn,
            "uru:c",
            r(ReferenceKind::URU, "uru:b"),
        ),
        (
            "cause",
            UnknownRelationKind::CausedBy,
            "uru:b",
            r(ReferenceKind::URU, "uru:a"),
        ),
        (
            "block",
            UnknownRelationKind::Blocks,
            "uru:a",
            r(ReferenceKind::RUO, "ruo:0"),
        ),
        (
            "related",
            UnknownRelationKind::RelatedTo,
            "uru:a",
            r(ReferenceKind::URU, "uru:c"),
        ),
        (
            "conflict",
            UnknownRelationKind::ConflictsWith,
            "uru:b",
            r(ReferenceKind::URU, "uru:c"),
        ),
    ] {
        let source = r(ReferenceKind::URU, source);
        let relation = UnknownRelation {
            id: format!("unknown-relation:{id}"),
            kind,
            source: source.clone(),
            target: target.clone(),
        };
        records.push(record(
            ReferenceKind::UnknownRelation,
            serde_json::to_value(relation).unwrap(),
            vec![source, target],
        ));
    }
    records.push(record(ReferenceKind::URU,json!({"id":"uru:a","known_information":{"fact":true},"missing_information":{"measurement":null},"evidence_refs":["evidence:1"],"knowledge_refs":["knowledge:1"],"causal_refs":[{"kind":"UnknownRelation","id":"unknown-relation:cause"}]}),vec![r(ReferenceKind::Evidence,"evidence:1"),r(ReferenceKind::Knowledge,"knowledge:1"),r(ReferenceKind::UnknownRelation,"unknown-relation:cause")]));
    let g = graph();
    let references = g
        .uru_refs
        .iter()
        .map(|id| r(ReferenceKind::URU, id))
        .chain(
            g.relation_refs
                .iter()
                .map(|id| r(ReferenceKind::UnknownRelation, id)),
        )
        .collect();
    records.push(record(
        ReferenceKind::URUS,
        serde_json::to_value(g).unwrap(),
        references,
    ));
    records.push(record(ReferenceKind::URUO,json!({"id":"uruo:1","space":"abstract","coordinate_frame":"frame","coordinate_unit":"unit","coordinate_bounds":[[-10.,10.],[-10.,10.],[-10.,10.]],"uru_refs":["uru:a","uru:b","uru:c"],"urus_refs":["urus:1"],"ruo_refs":["ruo:0"],"placements":[{"target":{"kind":"URU","id":"uru:a"},"status":"known","position":[1.,2.,3.]},{"target":{"kind":"URU","id":"uru:b"},"status":"unknown","position":null},{"target":{"kind":"URU","id":"uru:c"},"status":"unknown","position":null},{"target":{"kind":"URUS","id":"urus:1"},"status":"unknown","position":null}],"constraints":[{"kind":"DISTANCE","source":{"kind":"URU","id":"uru:a"},"target":{"kind":"URU","id":"uru:b"},"distance":null}]}),vec![r(ReferenceKind::URU,"uru:a"),r(ReferenceKind::URU,"uru:b"),r(ReferenceKind::URU,"uru:c"),r(ReferenceKind::URUS,"urus:1"),r(ReferenceKind::RUO,"ruo:0")]));
    RCPPayload {
        records,
        unknowns: vec![
            unit("uru:c", r(ReferenceKind::RUO, "ruo:0"), &["uru:b"]),
            unit("uru:a", r(ReferenceKind::RU, "ru:0"), &[]),
            unit("uru:b", r(ReferenceKind::RUS, "rus:0"), &["uru:a"]),
        ],
    }
}
struct Domain;
impl CandidateValidator for Domain {
    fn validate(&self, _: &UnknownUnit, candidate: &Value) -> RCPResult<()> {
        if candidate == "answer" {
            Ok(())
        } else {
            Err("domain rejected".into())
        }
    }
}
fn registry(p: &RCPPayload) -> UnknownRegistry {
    let mut registry = UnknownRegistry::default();
    for id in ["uru:a", "uru:b", "uru:c"] {
        registry
            .commit(
                p.unknowns.iter().find(|u| u.id == id).unwrap().clone(),
                p,
                &Domain,
            )
            .unwrap();
    }
    registry
}

#[test]
fn urs_t01_t03_independent_id_information_and_all_relations() {
    let p = payload();
    p.validate().unwrap();
    assert_eq!(p.unknowns[0].origins[0].kind, ReferenceKind::RUO);
    assert_eq!(p.unknowns[2].origins[0].kind, ReferenceKind::RUS);
    assert!(p
        .unknowns
        .iter()
        .all(|unit| unit.origins.iter().all(|origin| origin.id != unit.id)));
    assert_eq!(
        p.records
            .iter()
            .find(|r| r.reference.kind == ReferenceKind::URU)
            .unwrap()
            .value["missing_information"],
        json!({"measurement":null})
    );
    assert_eq!(
        p.records
            .iter()
            .filter(|r| r.reference.kind == ReferenceKind::UnknownRelation)
            .count(),
        6
    );
}
#[test]
fn urs_t02_registry_preserves_history_through_reopening() {
    let p = payload();
    let mut registry = registry(&p);
    let mut unit = registry.get("uru:a").unwrap().clone();
    for state in [
        UnknownState::InProgress,
        UnknownState::Candidate,
        UnknownState::Resolved,
        UnknownState::Reopened,
        UnknownState::Open,
        UnknownState::Blocked,
    ] {
        let before = unit.clone();
        let candidate = matches!(state, UnknownState::Candidate | UnknownState::Resolved)
            .then(|| json!("answer"));
        unit.history.push(UnknownRevision {
            state,
            evidence: if candidate.is_some() {
                vec![r(ReferenceKind::Evidence, "evidence:1")]
            } else {
                vec![]
            },
            candidate,
        });
        registry.commit(unit.clone(), &p, &Domain).unwrap();
        assert_eq!(unit.origins, before.origins);
        assert_eq!(unit.history[..before.history.len()], before.history);
    }
    let before = unit.clone();
    unit.history.push(UnknownRevision {
        state: UnknownState::Resolved,
        evidence: vec![r(ReferenceKind::Evidence, "evidence:1")],
        candidate: Some(json!("answer")),
    });
    assert!(registry.commit(unit, &p, &Domain).is_err());
    assert_eq!(registry.get("uru:a"), Some(&before));
}
#[test]
fn urs_t04_cycle_closure_and_relation_integrity() {
    let mut p = payload();
    p.unknowns
        .iter_mut()
        .find(|u| u.id == "uru:a")
        .unwrap()
        .dependencies = vec!["uru:c".into()];
    assert!(p.validate().is_err());
    let mut p = payload();
    p.unknowns[0].dependencies = vec!["uru:missing".into()];
    assert!(p.validate().is_err());
    let mut p = payload();
    p.records
        .iter_mut()
        .find(|r| r.reference.id == "unknown-relation:ba")
        .unwrap()
        .value["target"]["kind"] = json!("Knowledge");
    assert!(p.validate().is_err());
    let mut p = payload();
    p.records
        .iter_mut()
        .find(|r| r.reference.id == "unknown-relation:ba")
        .unwrap()
        .value["target"]["id"] = json!("uru:c");
    assert!(p.validate().is_err());
    let mut p = payload();
    p.records
        .iter_mut()
        .find(|r| r.reference.kind == ReferenceKind::URUS)
        .unwrap()
        .references
        .pop();
    assert!(p.validate().is_err());
    let p = payload();
    let registry = registry(&p);
    let mut g = graph();
    g.uru_refs.retain(|id| id != "uru:a");
    assert!(g.reevaluation_order(&registry).is_err());
}
#[test]
fn urs_t05_t06_order_unresolved_and_resolved_impact() {
    let p = payload();
    let mut registry = registry(&p);
    let g = graph();
    assert_eq!(
        g.reevaluation_order(&registry).unwrap(),
        vec!["uru:a", "uru:b", "uru:c"]
    );
    assert_eq!(
        g.unresolved(&registry).unwrap(),
        vec!["uru:a", "uru:b", "uru:c"]
    );
    assert_eq!(
        g.impact(&registry, "uru:a").unwrap(),
        vec!["uru:b", "uru:c"]
    );
    assert!(g.impact(&registry, "uru:missing").is_err());
    for id in ["uru:a", "uru:b", "uru:c"] {
        let mut unit = registry.get(id).unwrap().clone();
        for state in [
            UnknownState::InProgress,
            UnknownState::Candidate,
            UnknownState::Resolved,
        ] {
            let candidate = matches!(state, UnknownState::Candidate | UnknownState::Resolved)
                .then(|| json!("answer"));
            unit.history.push(UnknownRevision {
                state,
                evidence: if candidate.is_some() {
                    vec![r(ReferenceKind::Evidence, "evidence:1")]
                } else {
                    vec![]
                },
                candidate,
            });
            registry.commit(unit.clone(), &p, &Domain).unwrap();
        }
    }
    assert!(g.unresolved(&registry).unwrap().is_empty());
    assert_eq!(
        g.resolved_impact(&registry, "uru:a").unwrap(),
        vec!["uru:b", "uru:c"]
    );
    let mut reversed = g.clone();
    reversed.uru_refs.reverse();
    assert_eq!(
        reversed.reevaluation_order(&registry).unwrap(),
        g.reevaluation_order(&registry).unwrap()
    );
}
#[test]
fn urs_t07_unknown_coordinates_and_invalid_spatial_data() {
    let p = payload();
    let value = &p
        .records
        .iter()
        .find(|r| r.reference.kind == ReferenceKind::URUO)
        .unwrap()
        .value;
    assert_eq!(value["placements"][1]["position"], Value::Null);
    for damage in [
        "2d",
        "unknown_with_position",
        "known_without_position",
        "bounds",
        "outside",
        "bad_member",
        "constraint",
        "frame",
        "missing_placement",
    ] {
        let mut p = payload();
        let v = &mut p
            .records
            .iter_mut()
            .find(|r| r.reference.kind == ReferenceKind::URUO)
            .unwrap()
            .value;
        match damage {
            "2d" => v["placements"][0]["position"] = json!([1., 2.]),
            "unknown_with_position" => v["placements"][1]["position"] = json!([1., 2., 3.]),
            "known_without_position" => v["placements"][0]["position"] = Value::Null,
            "bounds" => v["coordinate_bounds"][0] = json!([10., -10.]),
            "outside" => v["placements"][0]["position"] = json!([100., 2., 3.]),
            "bad_member" => v["placements"][1]["target"]["kind"] = json!("RU"),
            "constraint" => v["constraints"][0]["distance"] = json!(-1.),
            "frame" => v["coordinate_frame"] = json!("another-frame"),
            _ => {
                v["placements"].as_array_mut().unwrap().pop();
            }
        }
        assert!(p.validate().is_err(), "{damage}");
    }
}
#[test]
fn urs_t08_t09_lossless_deterministic_dispatch() {
    let run = || {
        let message = RCPMessage {
            schema: SCHEMA.into(),
            protocol_version: VERSION.into(),
            message_id: "message:urs".into(),
            source: "dsn:a".into(),
            destination: "dsn:b".into(),
            kind: RCPKind::UnknownReport,
            correlation_id: "conversation:urs".into(),
            causation_id: None,
            trace: vec![],
            payload: payload(),
        };
        let bytes = message.encode().unwrap();
        assert_eq!(RCPMessage::decode(&bytes, 100000).unwrap(), message);
        let mut dispatcher = RCPDispatcher::new(RCPLimits {
            messages: 2,
            requests: 1,
            hops: 3,
            bytes: 100000,
        });
        dispatcher
            .router
            .register("dsn:a".into(), "core:a".into())
            .unwrap();
        dispatcher
            .router
            .register("dsn:b".into(), "core:b".into())
            .unwrap();
        dispatcher.dispatch(&bytes).unwrap();
        let receipt = dispatcher.receive("dsn:b").unwrap().remove(0);
        assert_eq!(receipt.payload, message.payload);
        serde_json::to_vec(&receipt).unwrap()
    };
    assert_eq!(run(), run());
}

#[test]
fn urs_reject_identity_collision_and_allow_uru_grounds_without_description() {
    let p = payload();
    let mut registry = registry(&p);
    let mut collision = p.unknowns[0].clone();
    collision.id = "ru:1".into();
    collision.dependencies.clear();
    assert!(registry.commit(collision, &p, &Domain).is_err());
    assert!(registry.get("ru:1").is_none());
    let mut unit = unit("uru:grounded", r(ReferenceKind::RU, "ru:0"), &[]);
    unit.grounds = vec![r(ReferenceKind::URU, "uru:c")];
    registry.commit(unit.clone(), &p, &Domain).unwrap();
    assert_eq!(registry.get(&unit.id), Some(&unit));
}
