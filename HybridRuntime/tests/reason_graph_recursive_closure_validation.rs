use reasonscript_hybrid_runtime::{
    ClosureTraceEventKind, GraphClosureEngine, GraphRelation, HybridReasonUnit, MathClosureEngine,
    MathValue, ReasonGraph, RuntimeError, State,
};
use std::collections::BTreeSet;

fn graph_with_edges(graph_id: &str, edges: &[(&str, &str)]) -> ReasonGraph {
    let mut graph = ReasonGraph::new(graph_id);
    for node in edges
        .iter()
        .flat_map(|(source, target)| [*source, *target])
        .collect::<BTreeSet<_>>()
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
fn rgc15_01_closure_reuse() {
    let mut graph = graph_with_edges(
        "RGC15-01",
        &[
            ("Dog", "Mammal"),
            ("Mammal", "Animal"),
            ("Animal", "LivingThing"),
        ],
    );
    let mut engine = GraphClosureEngine::new();

    engine.derive_recursive(&mut graph).unwrap();

    assert!(graph.has_relation("Dog", "IsA", "Animal"));
    assert!(graph.has_relation("Mammal", "IsA", "LivingThing"));
}

#[test]
fn rgc15_02_closure_of_closure() {
    let mut graph = graph_with_edges(
        "RGC15-02",
        &[
            ("Dog", "Mammal"),
            ("Mammal", "Animal"),
            ("Animal", "LivingThing"),
        ],
    );
    let mut engine = GraphClosureEngine::new();

    engine.derive_recursive(&mut graph).unwrap();

    let trace = engine
        .trace_logger
        .records()
        .iter()
        .find(|trace| {
            trace.closure_level == 2
                && trace
                    .derived_relation
                    .as_ref()
                    .is_some_and(|edge| edge.source == "Dog" && edge.target == "LivingThing")
        })
        .unwrap();
    assert_eq!(trace.source_relations.len(), 2);
}

#[test]
fn rgc15_03_recursive_closure_chain() {
    let mut graph = graph_with_edges(
        "RGC15-03",
        &[("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")],
    );
    let mut engine = GraphClosureEngine::new();

    let result = engine.derive_recursive(&mut graph).unwrap();

    for target in ["C", "D", "E"] {
        assert!(graph.has_relation("A", "IsA", target));
    }
    assert_eq!(result.closure_levels, 2);
}

#[test]
fn rgc15_04_closure_saturation() {
    let mut graph = ReasonGraph::new("RGC15-04");
    for node in ["Dog", "Mammal", "Animal", "LivingThing"] {
        graph.add_stable_node(node).unwrap();
    }
    let mut engine = GraphClosureEngine::new();

    let result = engine.derive_recursive(&mut graph).unwrap();

    assert!(result.saturated);
    assert!(result.derived_relations.is_empty());
    assert_eq!(
        engine.trace_logger.records()[0].trace_event_kind,
        ClosureTraceEventKind::Saturation
    );
}

#[test]
fn rgc15_05_duplicate_prevention() {
    let mut graph = graph_with_edges(
        "RGC15-05",
        &[
            ("Dog", "Mammal"),
            ("Mammal", "Animal"),
            ("Animal", "LivingThing"),
        ],
    );
    let mut engine = GraphClosureEngine::new();

    engine.derive_recursive(&mut graph).unwrap();
    engine.derive_recursive(&mut graph).unwrap();

    assert_eq!(
        graph
            .relations()
            .iter()
            .filter(|edge| edge.source == "Dog" && edge.target == "LivingThing")
            .count(),
        1
    );
}

#[test]
fn rgc15_06_cycle_protection() {
    let mut graph = graph_with_edges("RGC15-06", &[("A", "B"), ("B", "C"), ("C", "A")]);
    let mut engine = GraphClosureEngine::new();

    assert!(matches!(
        engine.derive_recursive(&mut graph),
        Err(RuntimeError::GraphCycleDetected { .. })
    ));
    assert_eq!(graph.edge_count(), 3);
}

#[test]
fn rgc15_07_closure_provenance() {
    let mut graph = graph_with_edges(
        "RGC15-07",
        &[
            ("Dog", "Mammal"),
            ("Mammal", "Animal"),
            ("Animal", "LivingThing"),
        ],
    );
    let mut engine = GraphClosureEngine::new();
    engine.set_trace_test_id("RGC15-07");

    engine.derive_recursive(&mut graph).unwrap();

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
    assert_eq!(trace.source_relations.len(), 2);
    assert_eq!(trace.closure_provenance.len(), 3);
    assert_eq!(trace.closure_level, 2);
}

#[test]
fn rgc15_08_graph_integrity() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));
    let before = serde_json::to_value(&unit).unwrap();
    let mut graph = graph_with_edges(
        "RGC15-08",
        &[
            ("Dog", "Mammal"),
            ("Mammal", "Animal"),
            ("Animal", "LivingThing"),
        ],
    );
    let mut engine = GraphClosureEngine::new();

    engine.derive_recursive(&mut graph).unwrap();

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
fn mr15_01_arithmetic_chain() {
    let mut engine = MathClosureEngine::new();
    let five = engine
        .add("MR15-01", MathValue::scalar(2.0), MathValue::scalar(3.0))
        .unwrap();
    let twenty = engine
        .multiply("MR15-01", five, MathValue::scalar(4.0))
        .unwrap();

    let result = engine
        .subtract("MR15-01", twenty, MathValue::scalar(8.0))
        .unwrap();

    assert_eq!(result, MathValue::scalar(12.0));
    assert_eq!(engine.trace_logger.records()[2].closure_level, 3);
}

#[test]
fn mr15_02_equation_transformation_chain() {
    let mut engine = MathClosureEngine::new();

    let result = engine
        .solve_linear_recursive("MR15-02", 2.0, 3.0, 7.0)
        .unwrap();

    assert_eq!(result, MathValue::scalar(2.0));
    assert_eq!(
        engine.trace_logger.records()[0]
            .final_state
            .as_stable()
            .unwrap()
            .identity,
        "2x = 4"
    );
    assert_eq!(
        engine.trace_logger.records()[1]
            .final_state
            .as_stable()
            .unwrap()
            .identity,
        "x = 2"
    );
}

#[test]
fn mr15_03_multi_step_equation() {
    let mut engine = MathClosureEngine::new();

    let result = engine
        .solve_linear_recursive("MR15-03", 3.0, 5.0, 20.0)
        .unwrap();

    assert_eq!(result, MathValue::scalar(5.0));
}

#[test]
fn mr15_04_derived_step_reuse() {
    let mut engine = MathClosureEngine::new();

    engine
        .solve_linear_recursive("MR15-04", 3.0, 5.0, 20.0)
        .unwrap();

    let traces = engine.trace_logger.records();
    assert_eq!(traces[1].visited_nodes[0], traces[0].visited_nodes[1]);
    assert_eq!(traces[1].closure_provenance.len(), 2);
}

#[test]
fn mr15_05_mathematical_provenance() {
    let mut engine = MathClosureEngine::new();
    engine.set_trace_test_id("MR15-05");

    engine
        .solve_linear_recursive("MR15-05", 3.0, 5.0, 20.0)
        .unwrap();

    let json = serde_json::to_value(engine.trace_logger.records()).unwrap();
    let trace = json.as_array().unwrap()[1].as_object().unwrap();
    for field in [
        "test_id",
        "graph_id",
        "closure_level",
        "source_relations",
        "derived_relation",
        "closure_provenance",
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
            "missing recursive trace field: {field}"
        );
    }
    assert_eq!(trace["closure_level"], 2);
    assert_eq!(trace["closure_provenance"].as_array().unwrap().len(), 2);
}
