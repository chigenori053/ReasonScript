use std::{
    collections::{BTreeMap, HashSet},
    fs,
    path::Path,
};

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::{
    canonical::{canonical_json, pretty_json},
    messages::{validate_stream, ClusterMessage},
};

pub const ARTIFACT_FILES: [&str; 9] = [
    "cluster_manifest.json",
    "cluster_plan.json",
    "cluster_nodes.json",
    "cluster_messages.jsonl",
    "cluster_trace.json",
    "cluster_state.json",
    "cluster_diagnostics.json",
    "cluster_evaluation_report.json",
    "cluster_run_summary.json",
];

pub fn write_artifacts(
    directory: &Path,
    documents: &BTreeMap<String, Value>,
) -> Result<Value, String> {
    fs::create_dir_all(directory).map_err(|e| format!("CRR-EVL-005: {e}"))?;
    for name in ARTIFACT_FILES.iter().skip(1) {
        let value = documents
            .get(*name)
            .ok_or_else(|| format!("CRR-EVL-005: missing document {name}"))?;
        let payload = if name.ends_with("jsonl") {
            value
                .as_array()
                .ok_or("CRR-EVL-005: message log must be an array")?
                .iter()
                .map(|item| canonical_json(item).map(|s| s + "\n"))
                .collect::<Result<String, _>>()
                .map_err(|e| e.to_string())?
        } else {
            pretty_json(value).map_err(|e| e.to_string())?
        };
        fs::write(directory.join(name), payload).map_err(|e| format!("CRR-EVL-005: {e}"))?;
    }
    let mut entries = Vec::new();
    for name in ARTIFACT_FILES.iter().skip(1) {
        let bytes = fs::read(directory.join(name)).map_err(|e| e.to_string())?;
        entries.push(json!({"file":name,"bytes":bytes.len(),"checksum":format!("sha256:{:x}",Sha256::digest(&bytes))}));
    }
    let mut manifest = documents["cluster_manifest.json"].clone();
    manifest["artifacts"] = Value::Array(entries);
    fs::write(
        directory.join("cluster_manifest.json"),
        pretty_json(&manifest).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    Ok(manifest)
}

pub fn validate_directory(directory: &Path) -> Value {
    let mut diagnostics = Vec::new();
    for name in ARTIFACT_FILES {
        if !directory.join(name).is_file() {
            diagnostics.push(json!({"code":"CRR-EVL-005","severity":"error","message":format!("Missing artifact: {name}"),"location":name}));
        }
    }
    if !diagnostics.is_empty() {
        return json!({"valid":false,"diagnostics":diagnostics});
    }
    let manifest: Value = match read_json(&directory.join("cluster_manifest.json")) {
        Ok(v) => v,
        Err(e) => return invalid(e),
    };
    for entry in manifest
        .get("artifacts")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let name = entry.get("file").and_then(Value::as_str).unwrap_or("");
        match fs::read(directory.join(name)) { Ok(bytes) if format!("sha256:{:x}",Sha256::digest(&bytes)) == entry.get("checksum").and_then(Value::as_str).unwrap_or("") => {}, _ => diagnostics.push(json!({"code":"CRR-EVL-003","severity":"error","message":"Artifact checksum mismatch","location":name})) }
    }
    let nodes: Value = match read_json(&directory.join("cluster_nodes.json")) {
        Ok(v) => v,
        Err(e) => return invalid(e),
    };
    let registered: HashSet<_> = nodes
        .get("nodes")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|n| n.get("node_id").and_then(Value::as_str).map(str::to_string))
        .collect();
    let text = match fs::read_to_string(directory.join("cluster_messages.jsonl")) {
        Ok(v) => v,
        Err(e) => return invalid(e.to_string()),
    };
    let messages: Result<Vec<ClusterMessage>, _> = text
        .lines()
        .filter(|line| !line.is_empty())
        .map(serde_json::from_str)
        .collect();
    match messages { Ok(items) => diagnostics.extend(validate_stream(&items, &registered, usize::MAX).into_iter().map(|d| serde_json::to_value(d).unwrap())), Err(e) => diagnostics.push(json!({"code":"CRR-EVL-005","severity":"error","message":e.to_string(),"location":"cluster_messages.jsonl"})) }
    json!({"valid":diagnostics.is_empty(),"diagnostics":diagnostics,"artifact_count":ARTIFACT_FILES.len()})
}

fn read_json(path: &Path) -> Result<Value, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}
fn invalid(message: String) -> Value {
    json!({"valid":false,"diagnostics":[{"code":"CRR-EVL-005","severity":"error","message":message}]})
}
