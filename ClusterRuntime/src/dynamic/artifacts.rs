use super::lifecycle::allowed;
use super::runtime::{canonical_unit_id, UnitProposal};
use crate::canonical::{canonical_json, pretty_json};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, HashMap, HashSet},
    fs,
    path::Path,
};

pub const DYNAMIC_ARTIFACT_FILES: [&str; 9] = [
    "dynamic_unit_manifest.json",
    "dynamic_unit_lifecycle.jsonl",
    "dynamic_unit_proposals.jsonl",
    "dynamic_plan_revisions.jsonl",
    "dynamic_branch_graph.json",
    "dynamic_pruning_report.json",
    "dynamic_convergence_report.json",
    "dynamic_budget_report.json",
    "dynamic_execution_summary.json",
];

pub fn write_dynamic_artifacts(
    dir: &Path,
    docs: &BTreeMap<String, Value>,
) -> Result<Value, String> {
    fs::create_dir_all(dir).map_err(|e| format!("DRU-ART-001: {e}"))?;
    for name in DYNAMIC_ARTIFACT_FILES.iter().skip(1) {
        let value = docs
            .get(*name)
            .ok_or_else(|| format!("DRU-ART-001: missing {name}"))?;
        let text = if name.ends_with("jsonl") {
            value
                .as_array()
                .ok_or_else(|| format!("DRU-ART-002: {name} must be an array"))?
                .iter()
                .map(|v| canonical_json(v).map(|x| x + "\n"))
                .collect::<Result<String, _>>()
                .map_err(|e| e.to_string())?
        } else {
            pretty_json(value).map_err(|e| e.to_string())?
        };
        fs::write(dir.join(name), text).map_err(|e| format!("DRU-ART-001: {e}"))?;
    }
    let mut entries = Vec::new();
    for name in DYNAMIC_ARTIFACT_FILES.iter().skip(1) {
        let bytes = fs::read(dir.join(name)).map_err(|e| e.to_string())?;
        entries.push(json!({"file":name,"bytes":bytes.len(),"checksum":format!("sha256:{:x}",Sha256::digest(&bytes))}));
    }
    let mut manifest = docs["dynamic_unit_manifest.json"].clone();
    manifest["artifacts"] = json!(entries);
    fs::write(
        dir.join("dynamic_unit_manifest.json"),
        pretty_json(&manifest).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    Ok(manifest)
}

pub fn validate_dynamic_directory(dir: &Path) -> Value {
    let missing:Vec<_>=DYNAMIC_ARTIFACT_FILES.iter().filter(|n|!dir.join(n).is_file()).map(|n|json!({"code":"DRU-ART-001","severity":"error","message":format!("Missing artifact: {n}"),"location":n})).collect();
    if !missing.is_empty() {
        return json!({"valid":false,"diagnostics":missing});
    }
    let mut docs = BTreeMap::new();
    for name in DYNAMIC_ARTIFACT_FILES {
        let text = match fs::read_to_string(dir.join(name)) {
            Ok(x) => x,
            Err(e) => return invalid("DRU-ART-001", e.to_string()),
        };
        let value = if name.ends_with("jsonl") {
            let parsed: Result<Vec<Value>, _> = text
                .lines()
                .filter(|x| !x.is_empty())
                .map(serde_json::from_str)
                .collect();
            match parsed {
                Ok(v) => json!(v),
                Err(e) => return invalid("DRU-ART-002", e.to_string()),
            }
        } else {
            match serde_json::from_str(&text) {
                Ok(v) => v,
                Err(e) => return invalid("DRU-ART-002", e.to_string()),
            }
        };
        docs.insert(name.into(), value);
    }
    let mut result = validate_documents(&docs);
    let mut diagnostics = result["diagnostics"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    for entry in docs["dynamic_unit_manifest.json"]["artifacts"]
        .as_array()
        .into_iter()
        .flatten()
    {
        let name = entry["file"].as_str().unwrap_or("");
        let actual = fs::read(dir.join(name))
            .ok()
            .map(|b| format!("sha256:{:x}", Sha256::digest(&b)));
        if actual.as_deref() != entry["checksum"].as_str() {
            diagnostics.push(diag("DRU-ART-002", "Artifact checksum mismatch", name));
        }
    }
    result["valid"] = json!(diagnostics.is_empty());
    result["diagnostics"] = json!(diagnostics);
    result
}

pub fn validate_documents(docs: &BTreeMap<String, Value>) -> Value {
    let mut ds = Vec::new();
    for name in DYNAMIC_ARTIFACT_FILES.iter().skip(1) {
        if !docs.contains_key(*name) {
            ds.push(diag(
                "DRU-ART-001",
                "Required dynamic artifact missing",
                name,
            ));
        }
    }
    if !ds.is_empty() {
        return json!({"valid":false,"diagnostics":ds});
    }
    let events = docs["dynamic_unit_lifecycle.jsonl"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let mut states = HashMap::<String, String>::new();
    for (i, e) in events.iter().enumerate() {
        if e["sequence"].as_u64() != Some((i + 1) as u64) {
            ds.push(diag(
                "DRU-ART-003",
                "Lifecycle sequence mismatch",
                "dynamic_unit_lifecycle.jsonl",
            ));
        }
        let id = e["reason_unit_id"].as_str().unwrap_or("");
        let from = e["from"].as_str();
        let current = states.get(id).map(String::as_str);
        if from != current || !allowed(current, e["to"].as_str().unwrap_or("")) {
            ds.push(diag("DRU-LFC-001", "Illegal lifecycle trace", id));
        }
        states.insert(id.into(), e["to"].as_str().unwrap_or("").into());
    }
    let proposals = docs["dynamic_unit_proposals.jsonl"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    if proposals.is_empty() {
        ds.push(diag(
            "DRU-ART-004",
            "Proposal trace missing",
            "dynamic_unit_proposals.jsonl",
        ));
    }
    let semantic_seed = docs
        .get("dynamic_unit_manifest.json")
        .and_then(|v| v["run_semantic_seed"].as_str())
        .unwrap_or("");
    let mut accepted_index = 0usize;
    for record in &proposals {
        match serde_json::from_value::<UnitProposal>(record["proposal"].clone()) {
            Ok(proposal) => {
                let valid_checksum = proposal.valid_checksum();
                if record["accepted"] == true {
                    accepted_index += 1;
                    if !valid_checksum {
                        ds.push(diag(
                            "DRU-PRP-005",
                            "Accepted proposal checksum mismatch",
                            &proposal.proposal_id,
                        ));
                    }
                    let expected = canonical_unit_id(semantic_seed, &proposal, accepted_index);
                    if record["reason_unit_id"].as_str() != Some(expected.as_str()) {
                        ds.push(diag(
                            "DRU-GEN-005",
                            "Canonical ReasonUnit ID mismatch",
                            &proposal.proposal_id,
                        ));
                    }
                } else if record["diagnostic"] == "DRU-PRP-005" && valid_checksum {
                    ds.push(diag(
                        "DRU-PRP-005",
                        "Checksum rejection is inconsistent",
                        &proposal.proposal_id,
                    ));
                }
            }
            Err(_) => ds.push(diag(
                "DRU-PRP-001",
                "Proposal trace schema invalid",
                "dynamic_unit_proposals.jsonl",
            )),
        }
    }
    let revisions = docs["dynamic_plan_revisions.jsonl"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let mut prior_revisions = Vec::new();
    for r in &revisions {
        if r["base_plan_checksum"].as_str()
            != crate::canonical::checksum(&prior_revisions).ok().as_deref()
        {
            ds.push(diag(
                "DRU-REV-001",
                "Revision base checksum mismatch",
                r["revision_id"].as_str().unwrap_or(""),
            ));
        }
        if r["atomic"] != true || r["applied"] != true {
            ds.push(diag(
                "DRU-REV-003",
                "Revision was not atomically applied",
                r["revision_id"].as_str().unwrap_or(""),
            ));
        }
        let mut body = r.clone();
        let stored = body
            .as_object_mut()
            .and_then(|m| m.remove("revision_checksum"));
        let actual = crate::canonical::checksum(&body).ok();
        if stored.as_ref().and_then(Value::as_str) != actual.as_deref() {
            ds.push(diag(
                "DRU-REV-002",
                "Revision checksum mismatch",
                r["revision_id"].as_str().unwrap_or(""),
            ));
        }
        prior_revisions.push(r.clone());
    }
    let graph = &docs["dynamic_branch_graph.json"];
    let unit_ids: HashSet<_> = graph["units"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|u| u["reason_unit_id"].as_str())
        .collect();
    for u in graph["units"].as_array().into_iter().flatten() {
        for parent in u["parent_unit_ids"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
        {
            if !unit_ids.contains(parent) {
                ds.push(diag(
                    "DRU-PRP-003",
                    "Parent unit missing from branch graph",
                    parent,
                ));
            }
        }
    }
    let b = &docs["dynamic_budget_report.json"];
    for key in [
        "units",
        "branches",
        "messages",
        "logical_steps",
        "state_bytes",
    ] {
        if b["usage"].get(key).is_none() {
            ds.push(diag("DRU-ART-006", "Budget accounting field missing", key));
        }
    }
    json!({"schema_version":"reasonscript-dynamic-artifact-validation/0.1","valid":ds.is_empty(),"artifact_count":DYNAMIC_ARTIFACT_FILES.len(),"diagnostics":ds})
}
fn diag(code: &str, message: &str, location: &str) -> Value {
    json!({"code":code,"severity":"error","message":message,"location":location})
}
fn invalid(code: &str, message: String) -> Value {
    json!({"valid":false,"diagnostics":[{"code":code,"severity":"error","message":message}]})
}
