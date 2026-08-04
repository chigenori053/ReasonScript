use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use crate::canonical::checksum;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct StateSnapshot {
    pub schema_version: String,
    pub run_id: String,
    pub logical_step: usize,
    pub state_version: usize,
    pub worker_states: Value,
    pub shared_state: Value,
    pub completed_tasks: Vec<String>,
    pub pending_tasks: Vec<String>,
    pub checksum: String,
}

impl StateSnapshot {
    pub fn new(
        run_id: &str,
        logical_step: usize,
        state_version: usize,
        worker_states: Value,
        shared_state: Value,
        mut completed_tasks: Vec<String>,
        mut pending_tasks: Vec<String>,
    ) -> Result<Self, serde_json::Error> {
        completed_tasks.sort();
        pending_tasks.sort();
        let body = serde_json::json!({"schema_version":"reasonscript-cluster-state/0.1","run_id":run_id,"logical_step":logical_step,"state_version":state_version,"worker_states":worker_states,"shared_state":shared_state,"completed_tasks":completed_tasks,"pending_tasks":pending_tasks});
        let digest = checksum(&body)?;
        Ok(Self {
            schema_version: "reasonscript-cluster-state/0.1".into(),
            run_id: run_id.into(),
            logical_step,
            state_version,
            worker_states: body["worker_states"].clone(),
            shared_state: body["shared_state"].clone(),
            completed_tasks: serde_json::from_value(body["completed_tasks"].clone())?,
            pending_tasks: serde_json::from_value(body["pending_tasks"].clone())?,
            checksum: digest,
        })
    }
}

pub fn merge(current: &Value, proposal: &Value, policy: &str) -> Result<Value, String> {
    match policy {
        "replace" => Ok(proposal.clone()),
        "append" => {
            let mut out = current.as_array().cloned().unwrap_or_default();
            out.extend(proposal.as_array().cloned().unwrap_or_default());
            Ok(Value::Array(out))
        }
        "set_union" => {
            let mut values: Vec<_> = current
                .as_array()
                .into_iter()
                .flatten()
                .chain(proposal.as_array().into_iter().flatten())
                .cloned()
                .collect();
            values.sort_by_key(|v| v.to_string());
            values.dedup();
            Ok(Value::Array(values))
        }
        "ordered_merge" => {
            let mut out: Map<String, Value> = current.as_object().cloned().unwrap_or_default();
            let mut keys: Vec<_> = proposal
                .as_object()
                .into_iter()
                .flat_map(|m| m.keys())
                .collect();
            keys.sort();
            for key in keys {
                out.insert(key.clone(), proposal[key].clone());
            }
            Ok(Value::Object(out))
        }
        "numeric_reduce" => match (current.as_f64(), proposal.as_f64()) {
            (Some(a), Some(b)) => Ok(serde_json::json!(a + b)),
            _ => Err("numeric_reduce requires numeric values".into()),
        },
        "custom_validated" => Err("custom_validated merge function is not registered".into()),
        _ => Err(format!("unknown merge policy: {policy}")),
    }
}
