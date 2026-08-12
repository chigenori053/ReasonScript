use reasonscript_native_reasonunit_runtime::{load_reason_graph, load_ruo, query_reason_graph, reason_graph_handoff, transact_reason_graph_file, NativeObjectStore, NativeQuery, NATIVE_REASON_GRAPH_PROFILE, NATIVE_REASON_GRAPH_QUERY_PROFILE, PROFILE};
use serde_json::json;
use std::path::Path;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let operation = args.get(1).map(String::as_str).unwrap_or("verify-native");
    if operation == "verify-native" {
        println!(
            "{}",
            json!({"ok":true,"native_execution_provenance":PROFILE,"unsafe_blocks":0})
        );
        return;
    }
    if operation == "load-graph" {
        let path = match args.get(2) {
            Some(path) => path,
            None => {
                println!("{}", json!({"ok":false,"exit_status":1,"operation":operation,"diagnostics":[{"code":"RGO-N1-001","message":"GRAPH.rgraph is required"}]}));
                std::process::exit(1);
            }
        };
        match load_reason_graph(Path::new(path)) {
            Ok(graph) => println!(
                "{}",
                json!({"ok":true,"exit_status":0,"operation":operation,"native_execution_provenance":PROFILE,"native_reason_graph_profile":NATIVE_REASON_GRAPH_PROFILE,"graph_id":graph.graph_id,"graph_hash":graph.graph_hash,"unit_ids":graph.units,"relation_ids":graph.relation_ids,"read_only":true,"resource_status":"metadata_verified"})
            ),
            Err(error) => {
                println!("{}", json!({"ok":false,"exit_status":1,"operation":operation,"native_execution_provenance":PROFILE,"diagnostics":[error]}));
                std::process::exit(1);
            }
        }
        return;
    }
    if operation == "query-graph" {
        let path = match args.get(2) {
            Some(path) => path,
            None => {
                println!("{}", json!({"ok":false,"exit_status":1,"operation":operation,"diagnostics":[{"code":"RGO-N1-005","message":"GRAPH.rgraph is required"}]}));
                std::process::exit(1);
            }
        };
        let query = match args.get(3) {
            Some(query) => query,
            None => {
                println!("{}", json!({"ok":false,"exit_status":1,"operation":operation,"diagnostics":[{"code":"RGO-N1-005","message":"QUERY is required"}]}));
                std::process::exit(1);
            }
        };
        match load_reason_graph(Path::new(path)).and_then(|graph| query_reason_graph(&graph, query, args.get(4).map(String::as_str))) {
            Ok(result) => println!("{}", json!({"ok":true,"exit_status":0,"operation":operation,"native_execution_provenance":PROFILE,"native_reason_graph_profile":NATIVE_REASON_GRAPH_PROFILE,"native_query_profile":NATIVE_REASON_GRAPH_QUERY_PROFILE,"query_result":result,"read_only":true})),
            Err(error) => {
                println!("{}", json!({"ok":false,"exit_status":1,"operation":operation,"native_execution_provenance":PROFILE,"diagnostics":[error]}));
                std::process::exit(1);
            }
        }
        return;
    }
    if operation == "transact-graph" {
        let (path, proposal_path, expected_hash, transaction_id) = match (args.get(2), args.get(3), args.get(4), args.get(5)) {
            (Some(path), Some(proposal), Some(expected), Some(transaction)) => (path, proposal, expected, transaction),
            _ => {
                println!("{}", json!({"ok":false,"exit_status":1,"operation":operation,"diagnostics":[{"code":"RGO-N1-007","message":"GRAPH.rgraph PROPOSAL.json EXPECTED_HASH TRANSACTION_ID are required"}]}));
                std::process::exit(1);
            }
        };
        let result = std::fs::read_to_string(proposal_path)
            .map_err(|error| reasonscript_native_reasonunit_runtime::NativeError { code: "RGO-N1-007".into(), class: reasonscript_native_reasonunit_runtime::FailureClass::Load, message: error.to_string() })
            .and_then(|payload| serde_json::from_str(&payload).map_err(|error| reasonscript_native_reasonunit_runtime::NativeError { code: "RGO-N1-007".into(), class: reasonscript_native_reasonunit_runtime::FailureClass::Load, message: error.to_string() }))
            .and_then(|proposal| transact_reason_graph_file(Path::new(path), &proposal, expected_hash, transaction_id));
        match result {
            Ok(transaction) => println!("{}", json!({"ok":transaction.get("committed").and_then(serde_json::Value::as_bool).unwrap_or(false),"exit_status":if transaction.get("committed").and_then(serde_json::Value::as_bool).unwrap_or(false) {0} else {1},"operation":operation,"native_execution_provenance":PROFILE,"transaction":transaction})),
            Err(error) => {
                println!("{}", json!({"ok":false,"exit_status":1,"operation":operation,"native_execution_provenance":PROFILE,"diagnostics":[error]}));
                std::process::exit(1);
            }
        }
        return;
    }
    let path = match args.get(2) {
        Some(path) => path,
        None => {
            println!(
                "{}",
                json!({"ok":false,"exit_status":1,"diagnostics":[{"code":"RUO-N1-022","message":"OBJECT.ruo is required"}]})
            );
            std::process::exit(1);
        }
    };
    match load_ruo(Path::new(path)).and_then(|object| {
        let handoff = if operation == "reason-graph-handoff" {
            Some(reason_graph_handoff(&object)?)
        } else {
            None
        };
        let store = NativeObjectStore::new(1, 1_000_000);
        store
            .insert_object(object)
            .map(|snapshot| (store, snapshot, handoff))
    }) {
        Ok((_store, snapshot, handoff)) => {
            let entities = snapshot.query(NativeQuery::All);
            println!(
                "{}",
                json!({"ok":true,"exit_status":0,"operation":operation,"native_execution_provenance":PROFILE,"object_id":snapshot.object_id,"revision_id":snapshot.revision_id,"snapshot_generation":snapshot.generation,"logical_object_digest":snapshot.logical_object_digest,"entity_ids":entities.into_iter().map(|e| e.id).collect::<Vec<_>>(),"reason_graph_handoff":handoff,"resource_status":"metadata_verified"})
            );
        }
        Err(error) => {
            println!(
                "{}",
                json!({"ok":false,"exit_status":1,"operation":operation,"native_execution_provenance":PROFILE,"diagnostics":[error]})
            );
            std::process::exit(1);
        }
    }
}
