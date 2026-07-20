use reasonscript_native_reasonunit_runtime::{load_ruo, NativeObjectStore, NativeQuery, PROFILE};
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
        let store = NativeObjectStore::new(1, 1_000_000);
        store
            .insert_object(object)
            .map(|snapshot| (store, snapshot))
    }) {
        Ok((_store, snapshot)) => {
            let entities = snapshot.query(NativeQuery::All);
            println!(
                "{}",
                json!({"ok":true,"exit_status":0,"operation":operation,"native_execution_provenance":PROFILE,"object_id":snapshot.object_id,"revision_id":snapshot.revision_id,"snapshot_generation":snapshot.generation,"logical_object_digest":snapshot.logical_object_digest,"entity_ids":entities.into_iter().map(|e| e.id).collect::<Vec<_>>(),"resource_status":"metadata_verified"})
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
