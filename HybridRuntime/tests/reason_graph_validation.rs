use reasonscript_hybrid_runtime::{
    GraphRelation, GraphTraceEventKind, HybridReasonUnit, ReasonGraph, ReasonGraphRuntime,
    RuntimeError, State,
};

fn taxonomy_graph() -> ReasonGraph {
    let mut graph = ReasonGraph::new("taxonomy");
    for node in ["Dog", "Mammal", "Animal"] {
        graph.add_stable_node(node).unwrap();
    }
    graph
        .add_relation(GraphRelation::new("Dog", "IsA", "Mammal"))
        .unwrap();
    graph
        .add_relation(GraphRelation::new("Mammal", "IsA", "Animal"))
        .unwrap();
    graph
}

#[test]
fn rg_01_graph_construction() {
    let graph = taxonomy_graph();

    assert_eq!(graph.node_count(), 3);
    assert_eq!(graph.edge_count(), 2);
    assert_eq!(
        graph
            .node("Dog")
            .unwrap()
            .state()
            .as_stable()
            .unwrap()
            .identity,
        "Dog"
    );
}

#[test]
fn rg_02_node_integrity() {
    let graph = taxonomy_graph();
    let serialized = serde_json::to_value(graph.node("Dog").unwrap()).unwrap();

    assert_eq!(
        serialized
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>(),
        vec!["state"]
    );
}

#[test]
fn rg_03_neighbor_query() {
    let graph = taxonomy_graph();

    assert_eq!(graph.neighbors("Dog").unwrap(), vec!["Mammal"]);
}

#[test]
fn rg_04_parent_query() {
    let graph = taxonomy_graph();

    assert_eq!(graph.parents("Dog").unwrap(), vec!["Mammal"]);
}

#[test]
fn rg_05_child_query() {
    let graph = taxonomy_graph();

    assert_eq!(graph.children("Animal").unwrap(), vec!["Mammal"]);
}

#[test]
fn rg_06_path_discovery() {
    let graph = taxonomy_graph();
    let path = graph.find_path("Dog", "Animal").unwrap();

    assert_eq!(path.nodes, vec!["Dog", "Mammal", "Animal"]);
    assert_eq!(path.edges.len(), 2);
}

#[test]
fn rg_07_graph_transition() {
    let mut runtime = ReasonGraphRuntime::new(taxonomy_graph(), "Dog").unwrap();
    runtime.set_trace_test_id("RG-07");

    let state = runtime.transition("IsA").unwrap();

    assert_eq!(state.as_stable().unwrap().identity, "Mammal");
    assert_eq!(runtime.current_node(), "Mammal");
    assert_eq!(
        runtime.trace_logger.records()[0].trace_event_kind,
        GraphTraceEventKind::Transition
    );
}

#[test]
fn rg_08_multi_hop_reasoning() {
    let mut runtime = ReasonGraphRuntime::new(taxonomy_graph(), "Dog").unwrap();
    runtime.set_trace_test_id("RG-08");

    let state = runtime.infer_to("Animal").unwrap();

    assert_eq!(state.as_stable().unwrap().identity, "Animal");
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(trace.visited_nodes, vec!["Dog", "Mammal", "Animal"]);
    assert_eq!(trace.visited_edges.len(), 2);
    assert_eq!(trace.trace_event_kind, GraphTraceEventKind::Reasoning);
}

#[test]
fn rg_09_branch_graph() {
    let mut graph = ReasonGraph::new("branch");
    for node in ["Dog", "Mammal", "Pet", "Canine"] {
        graph.add_stable_node(node).unwrap();
    }
    for (relation, target) in [("IsA", "Mammal"), ("IsPet", "Pet"), ("IsA", "Canine")] {
        graph
            .add_relation(GraphRelation::new("Dog", relation, target))
            .unwrap();
    }

    assert_eq!(graph.outgoing("Dog").unwrap().len(), 3);
    assert_eq!(graph.edge_count(), 3);
}

#[test]
fn rg_10_converging_graph() {
    let mut graph = ReasonGraph::new("converging");
    for node in ["Dog", "Wolf", "Mammal"] {
        graph.add_stable_node(node).unwrap();
    }
    graph
        .add_relation(GraphRelation::new("Dog", "IsA", "Mammal"))
        .unwrap();
    graph
        .add_relation(GraphRelation::new("Wolf", "IsA", "Mammal"))
        .unwrap();

    assert_eq!(graph.children("Mammal").unwrap(), vec!["Dog", "Wolf"]);
    assert_eq!(graph.edge_count(), 2);
}

#[test]
fn rg_11_decision_driven_path_selection() {
    let mut graph = ReasonGraph::new("decision");
    for node in ["Dog", "Pet", "Mammal"] {
        graph.add_stable_node(node).unwrap();
    }
    graph
        .add_relation(GraphRelation::with_cost("Dog", "IsPet", "Pet", 0.10))
        .unwrap();
    graph
        .add_relation(GraphRelation::with_cost("Dog", "IsA", "Mammal", 0.40))
        .unwrap();
    let mut runtime = ReasonGraphRuntime::new(graph, "Dog").unwrap();
    runtime.set_trace_test_id("RG-11");

    let state = runtime.decide_and_transition().unwrap();

    assert_eq!(state.as_stable().unwrap().identity, "Pet");
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(
        trace.selected_path.as_ref().unwrap().nodes,
        vec!["Dog", "Pet"]
    );
    assert_eq!(trace.alternative_paths.len(), 1);
    assert!(trace.decision_reason.contains("minimum expected"));
    assert_eq!(trace.path_cost, Some(0.10));
}

#[test]
fn rg_12_graph_conflict_detection() {
    let mut graph = ReasonGraph::new("conflict");
    for node in ["StateX", "Y", "Z"] {
        graph.add_stable_node(node).unwrap();
    }
    graph
        .add_relation(GraphRelation::with_cost("StateX", "A", "Y", 0.25))
        .unwrap();
    graph
        .add_relation(GraphRelation::with_cost("StateX", "B", "Z", 0.25))
        .unwrap();
    let mut runtime = ReasonGraphRuntime::new(graph, "StateX").unwrap();
    runtime.set_trace_test_id("RG-12");

    let result = runtime.decide_and_transition();

    assert_eq!(
        result,
        Err(RuntimeError::GraphDecisionRequired {
            source: "StateX".to_string(),
            candidate_count: 2,
        })
    );
    assert_eq!(runtime.current_node(), "StateX");
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(trace.trace_event_kind, GraphTraceEventKind::Conflict);
    assert!(trace.selected_path.is_none());
    assert_eq!(trace.available_paths.len(), 2);
    assert!(trace.decision_reason.contains("decision required"));
}

#[test]
fn rg_13_graph_trace_validation() {
    let mut runtime = ReasonGraphRuntime::new(taxonomy_graph(), "Dog").unwrap();
    runtime.set_trace_test_id("RG-13");
    runtime.infer_to("Animal").unwrap();

    let json = serde_json::to_value(runtime.trace_logger.records()).unwrap();
    let trace = json.as_array().unwrap()[0].as_object().unwrap();
    for field in [
        "test_id",
        "graph_id",
        "start_node",
        "target_node",
        "visited_nodes",
        "visited_edges",
        "available_paths",
        "selected_path",
        "alternative_paths",
        "decision_reason",
        "path_cost",
        "final_state",
        "trace_event_kind",
        "policy_version",
        "evaluator_version",
    ] {
        assert!(
            trace.contains_key(field),
            "missing graph trace field: {field}"
        );
    }
    assert_eq!(trace["test_id"], "RG-13");
    assert_eq!(trace["graph_id"], "taxonomy");
}

#[test]
fn rg_14_graph_integrity_validation() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));
    let serialized_before = serde_json::to_value(&unit).unwrap();
    let mut graph = ReasonGraph::new("integrity");
    graph.add_node("Dog", unit.clone()).unwrap();
    graph.add_stable_node("Mammal").unwrap();
    graph
        .add_relation(GraphRelation::new("Dog", "IsA", "Mammal"))
        .unwrap();
    let serialized_after = serde_json::to_value(graph.node("Dog").unwrap()).unwrap();

    assert_eq!(serialized_before, serialized_after);
    assert_eq!(
        serialized_after
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>(),
        vec!["state"]
    );
    assert_eq!(graph.edge_count(), 1);
}
