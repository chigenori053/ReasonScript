use reasonscript_hybrid_runtime::{
    ClosureTraceEventKind, GraphClosureEngine, GraphRelation, HybridReasonUnit, MathClosureEngine,
    MathValue, ReasonGraph, RuntimeError, State,
};

fn graph_with_edges(graph_id: &str, edges: &[(&str, &str)]) -> ReasonGraph {
    let mut graph = ReasonGraph::new(graph_id);
    for node in edges
        .iter()
        .flat_map(|(source, target)| [*source, *target])
        .collect::<std::collections::BTreeSet<_>>()
    {
        graph.add_stable_node(node).unwrap();
    }
    for (source, target) in edges {
        graph
            .add_relation(GraphRelation::new(*source, "IsA", *target))
            .unwrap();
    }
    graph
}

#[test]
fn rgc_01_simple_transitive_closure() {
    let mut graph = graph_with_edges("RGC-01", &[("Dog", "Mammal"), ("Mammal", "Animal")]);
    let mut engine = GraphClosureEngine::new();

    let result = engine.derive_all(&mut graph).unwrap();

    assert!(graph.has_relation("Dog", "IsA", "Animal"));
    assert_eq!(result.derived_relations.len(), 1);
}

#[test]
fn rgc_02_multi_hop_closure() {
    let mut graph = graph_with_edges(
        "RGC-02",
        &[
            ("Dog", "Canine"),
            ("Canine", "Mammal"),
            ("Mammal", "Animal"),
            ("Animal", "LivingThing"),
        ],
    );
    let mut engine = GraphClosureEngine::new();

    engine.derive_all(&mut graph).unwrap();

    assert!(graph.has_relation("Dog", "IsA", "LivingThing"));
    let trace = engine
        .trace_logger
        .records()
        .iter()
        .find(|trace| {
            trace
                .derived_relation
                .as_ref()
                .is_some_and(|edge| edge.source == "Dog" && edge.target == "LivingThing")
        })
        .unwrap();
    assert_eq!(trace.source_relations.len(), 4);
}

#[test]
fn rgc_03_branch_closure_retains_both_paths() {
    let mut graph = graph_with_edges("RGC-03", &[("Dog", "Mammal"), ("Dog", "Pet")]);
    let before = graph.relations().to_vec();
    let mut engine = GraphClosureEngine::new();

    engine.derive_all(&mut graph).unwrap();

    assert_eq!(graph.relations(), before);
    assert_eq!(graph.outgoing("Dog").unwrap().len(), 2);
}

#[test]
fn rgc_04_converging_closure_is_consistent() {
    let mut graph = graph_with_edges("RGC-04", &[("Dog", "Mammal"), ("Wolf", "Mammal")]);
    let mut engine = GraphClosureEngine::new();

    engine.derive_all(&mut graph).unwrap();

    assert!(graph.has_relation("Dog", "IsA", "Mammal"));
    assert!(graph.has_relation("Wolf", "IsA", "Mammal"));
    assert_eq!(graph.edge_count(), 2);
}

#[test]
fn rgc_05_closure_trace_preserves_sources() {
    let mut graph = graph_with_edges("RGC-05", &[("Dog", "Mammal"), ("Mammal", "Animal")]);
    let mut engine = GraphClosureEngine::new();
    engine.set_trace_test_id("RGC-05");

    engine.derive_all(&mut graph).unwrap();

    let trace = &engine.trace_logger.records()[0];
    assert_eq!(trace.test_id.as_deref(), Some("RGC-05"));
    assert_eq!(trace.source_relations.len(), 2);
    assert_eq!(trace.derived_relation.as_ref().unwrap().source, "Dog");
    assert_eq!(trace.derived_relation.as_ref().unwrap().target, "Animal");
}

#[test]
fn rgc_06_duplicate_closure_prevention() {
    let mut graph = graph_with_edges(
        "RGC-06",
        &[("Dog", "Animal"), ("Dog", "Mammal"), ("Mammal", "Animal")],
    );
    let mut engine = GraphClosureEngine::new();

    engine.derive_all(&mut graph).unwrap();

    assert_eq!(
        graph
            .relations()
            .iter()
            .filter(|edge| edge.source == "Dog" && edge.target == "Animal")
            .count(),
        1
    );
}

#[test]
fn rgc_07_cycle_detection_prevents_derivation() {
    let mut graph = graph_with_edges("RGC-07", &[("A", "B"), ("B", "C"), ("C", "A")]);
    let mut engine = GraphClosureEngine::new();

    let result = engine.derive_all(&mut graph);

    assert!(matches!(
        result,
        Err(RuntimeError::GraphCycleDetected { .. })
    ));
    assert_eq!(graph.edge_count(), 3);
    assert_eq!(
        engine.trace_logger.records()[0].trace_event_kind,
        ClosureTraceEventKind::CycleDetected
    );
}

#[test]
fn rgc_08_closure_integrity_keeps_state_only_in_reason_unit() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));
    let before = serde_json::to_value(&unit).unwrap();
    let mut graph = graph_with_edges("RGC-08", &[("Dog", "Mammal"), ("Mammal", "Animal")]);
    let mut engine = GraphClosureEngine::new();

    engine.derive_all(&mut graph).unwrap();

    assert_eq!(
        serde_json::to_value(graph.node("Dog").unwrap()).unwrap(),
        before
    );
    assert_eq!(
        before.as_object().unwrap().keys().collect::<Vec<_>>(),
        vec!["state"]
    );
}

#[test]
fn mr_01_arithmetic_closure() {
    let mut engine = MathClosureEngine::new();

    let result = engine
        .add("MR-01", MathValue::scalar(2.0), MathValue::scalar(3.0))
        .unwrap();

    assert_eq!(result, MathValue::scalar(5.0));
}

#[test]
fn mr_02_sequential_arithmetic() {
    let mut engine = MathClosureEngine::new();
    let intermediate = engine
        .add("MR-02", MathValue::scalar(2.0), MathValue::scalar(3.0))
        .unwrap();

    let result = engine
        .multiply("MR-02", intermediate, MathValue::scalar(4.0))
        .unwrap();

    assert_eq!(result, MathValue::scalar(20.0));
    assert_eq!(engine.trace_logger.records().len(), 2);
}

#[test]
fn mr_03_inverse_operation() {
    let mut engine = MathClosureEngine::new();

    let result = engine.solve_linear("MR-03", 1.0, 3.0, 5.0).unwrap();

    assert_eq!(result, MathValue::scalar(2.0));
}

#[test]
fn mr_04_unit_preservation() {
    let mut engine = MathClosureEngine::new();

    let result = engine
        .add(
            "MR-04",
            MathValue::with_unit(3.0, "apples"),
            MathValue::with_unit(2.0, "apples"),
        )
        .unwrap();

    assert_eq!(result, MathValue::with_unit(5.0, "apples"));
    assert_eq!(
        engine.trace_logger.records()[0]
            .final_state
            .as_stable()
            .unwrap()
            .identity,
        "5 apples"
    );
}

#[test]
fn mr_05_linear_equation() {
    let mut engine = MathClosureEngine::new();

    let result = engine.solve_linear("MR-05", 2.0, 3.0, 7.0).unwrap();

    assert_eq!(result, MathValue::scalar(2.0));
}

#[test]
fn mr_06_mathematical_trace() {
    let mut engine = MathClosureEngine::new();
    engine.set_trace_test_id("MR-06");

    engine.solve_linear("MR-06", 2.0, 3.0, 7.0).unwrap();

    let json = serde_json::to_value(engine.trace_logger.records()).unwrap();
    let trace = json.as_array().unwrap()[0].as_object().unwrap();
    for field in [
        "test_id",
        "graph_id",
        "closure_id",
        "source_relations",
        "derived_relation",
        "visited_nodes",
        "visited_edges",
        "derivation_steps",
        "decision_reason",
        "final_state",
        "trace_event_kind",
        "policy_version",
        "evaluator_version",
    ] {
        assert!(
            trace.contains_key(field),
            "missing closure trace field: {field}"
        );
    }
    assert_eq!(
        trace["derivation_steps"],
        serde_json::json!(["2x + 3 = 7", "2x = 4", "x = 2"])
    );
}
