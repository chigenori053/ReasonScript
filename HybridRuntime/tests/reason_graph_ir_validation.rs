use reasonscript_hybrid_runtime::{
    GraphClosureEngine, GraphIRConversionType, GraphIRConverter, GraphIRTraceEventKind,
    GraphRelation, HybridReasonUnit, MathClosureEngine, ReasonGraph, State,
};
use std::collections::BTreeSet;

fn taxonomy_graph(graph_id: &str) -> ReasonGraph {
    let mut graph = ReasonGraph::new(graph_id);
    for node in ["Dog", "Mammal", "Animal", "LivingThing"] {
        graph.add_stable_node(node).unwrap();
    }
    for (source, target) in [
        ("Dog", "Mammal"),
        ("Mammal", "Animal"),
        ("Animal", "LivingThing"),
    ] {
        graph
            .add_relation(GraphRelation::new(source, "IsA", target))
            .unwrap();
    }
    graph
}

fn recursive_graph_ir(graph_id: &str) -> (ReasonGraph, reasonscript_hybrid_runtime::GraphIR) {
    let mut graph = taxonomy_graph(graph_id);
    let mut closure_engine = GraphClosureEngine::new();
    closure_engine.derive_recursive(&mut graph).unwrap();
    let mut converter = GraphIRConverter::new();
    let ir = converter.graph_to_ir(&graph, closure_engine.trace_logger.records());
    (graph, ir)
}

#[test]
fn rgir_01_graph_to_ir() {
    let graph = taxonomy_graph("RGIR-01");
    let mut converter = GraphIRConverter::new();

    let ir = converter.graph_to_ir(&graph, &[]);

    assert_eq!(ir.graph_id, "RGIR-01");
    assert_eq!(ir.nodes.len(), 4);
    assert_eq!(ir.relations.len(), 3);
}

#[test]
fn rgir_02_ir_to_graph() {
    let graph = taxonomy_graph("RGIR-02");
    let mut converter = GraphIRConverter::new();
    let ir = converter.graph_to_ir(&graph, &[]);

    let reconstructed = converter.ir_to_graph(&ir).unwrap();

    assert_eq!(reconstructed.graph.graph_id(), graph.graph_id());
    assert_eq!(reconstructed.graph.node_count(), graph.node_count());
    assert_eq!(reconstructed.graph.relations(), graph.relations());
}

#[test]
fn rgir_03_node_preservation() {
    let graph = taxonomy_graph("RGIR-03");
    let mut converter = GraphIRConverter::new();

    let ir = converter.graph_to_ir(&graph, &[]);

    assert_eq!(
        ir.nodes
            .iter()
            .map(|node| node.node_id.as_str())
            .collect::<BTreeSet<_>>(),
        BTreeSet::from(["Animal", "Dog", "LivingThing", "Mammal"])
    );
}

#[test]
fn rgir_04_relation_preservation() {
    let graph = taxonomy_graph("RGIR-04");
    let mut converter = GraphIRConverter::new();

    let ir = converter.graph_to_ir(&graph, &[]);

    assert_eq!(ir.relations.len(), graph.edge_count());
    assert!(ir
        .relations
        .iter()
        .any(|edge| edge.source == "Dog" && edge.target == "Mammal"));
}

#[test]
fn rgir_05_closure_preservation() {
    let (_, ir) = recursive_graph_ir("RGIR-05");

    let closure = ir
        .closures
        .iter()
        .find(|closure| {
            closure.derived_relation.source == "Dog" && closure.derived_relation.target == "Animal"
        })
        .unwrap();

    assert_eq!(closure.source_relations.len(), 2);
    assert_eq!(closure.closure_level, 1);
}

#[test]
fn rgir_06_recursive_closure_preservation() {
    let (_, ir) = recursive_graph_ir("RGIR-06");

    let closure = ir
        .closures
        .iter()
        .find(|closure| {
            closure.derived_relation.source == "Dog"
                && closure.derived_relation.target == "LivingThing"
        })
        .unwrap();

    assert_eq!(closure.closure_level, 2);
}

#[test]
fn rgir_07_provenance_preservation() {
    let (_, ir) = recursive_graph_ir("RGIR-07");
    let relation_id = GraphRelation::new("Dog", "IsA", "LivingThing").id();

    let provenance = ir
        .provenance
        .iter()
        .find(|entry| entry.relation_id == relation_id)
        .unwrap();

    assert_eq!(provenance.ancestry.len(), 3);
}

#[test]
fn rgir_08_round_trip_integrity() {
    let (graph, ir) = recursive_graph_ir("RGIR-08");
    let mut converter = GraphIRConverter::new();

    let reconstructed = converter.ir_to_graph(&ir).unwrap();

    assert_eq!(reconstructed.graph.node_count(), graph.node_count());
    assert_eq!(reconstructed.graph.edge_count(), graph.edge_count());
    assert_eq!(reconstructed.closures.len(), ir.closures.len());
    assert_eq!(reconstructed.provenance.len(), ir.provenance.len());
}

#[test]
fn rgir_09_mathematical_ir() {
    let mut math = MathClosureEngine::new();
    math.solve_linear_recursive("RGIR-09", 2.0, 3.0, 7.0)
        .unwrap();
    let mut converter = GraphIRConverter::new();

    let ir = converter.mathematical_to_ir("RGIR-09", math.trace_logger.records());

    assert_eq!(
        ir.mathematical_steps(),
        vec![
            ("2x + 3 = 7".to_string(), "2x = 4".to_string()),
            ("2x = 4".to_string(), "x = 2".to_string()),
        ]
    );
}

#[test]
fn rgir_10_mathematical_round_trip() {
    let mut math = MathClosureEngine::new();
    math.solve_linear_recursive("RGIR-10", 2.0, 3.0, 7.0)
        .unwrap();
    let mut converter = GraphIRConverter::new();
    let ir = converter.mathematical_to_ir("RGIR-10", math.trace_logger.records());

    let json = ir.to_json_pretty().unwrap();
    let restored: reasonscript_hybrid_runtime::GraphIR = serde_json::from_str(&json).unwrap();

    assert_eq!(restored, ir);
    assert_eq!(restored.mathematical_steps(), ir.mathematical_steps());
}

#[test]
fn rgir_11_ir_trace_validation() {
    let graph = taxonomy_graph("RGIR-11");
    let mut converter = GraphIRConverter::new();
    converter.set_trace_test_id("RGIR-11");
    let ir = converter.graph_to_ir(&graph, &[]);
    converter.ir_to_graph(&ir).unwrap();

    let json = serde_json::to_value(converter.trace_logger.records()).unwrap();
    let trace = json.as_array().unwrap()[0].as_object().unwrap();
    for field in [
        "test_id",
        "graph_id",
        "ir_id",
        "conversion_type",
        "node_count",
        "relation_count",
        "closure_count",
        "provenance_count",
        "derived_relations",
        "trace_event_kind",
        "policy_version",
        "evaluator_version",
    ] {
        assert!(trace.contains_key(field), "missing IR trace field: {field}");
    }
    assert_eq!(
        converter.trace_logger.records()[0].conversion_type,
        GraphIRConversionType::GraphToIR
    );
    assert_eq!(
        converter.trace_logger.records()[1].trace_event_kind,
        GraphIRTraceEventKind::Reconstruction
    );
}

#[test]
fn rgir_12_reason_unit_integrity() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));
    let before = serde_json::to_value(&unit).unwrap();
    let graph = taxonomy_graph("RGIR-12");
    let mut converter = GraphIRConverter::new();

    let ir = converter.graph_to_ir(&graph, &[]);
    let reconstructed = converter.ir_to_graph(&ir).unwrap();

    assert_eq!(
        serde_json::to_value(reconstructed.graph.node("Dog").unwrap()).unwrap(),
        before
    );
    assert_eq!(
        before.as_object().unwrap().keys().collect::<Vec<_>>(),
        vec!["state"]
    );
}
