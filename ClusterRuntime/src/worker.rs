use std::{
    io::Write,
    path::PathBuf,
    process::{Command, Stdio},
};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::planner::ReasonTask;

/// Runtime-host connection settings propagated to each isolated worker process.
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct RuntimeContext {
    pub host: Option<PathBuf>,
    pub resource_root: Option<PathBuf>,
    #[serde(default)]
    pub filesystem_read: bool,
    #[serde(default)]
    pub filesystem_write: bool,
    #[serde(default = "default_backend")]
    pub backend: String,
}

fn default_backend() -> String {
    "RuntimeReal".into()
}

pub fn execute(
    task: &ReasonTask,
    state_version: usize,
    context: &RuntimeContext,
) -> Result<Value, String> {
    let mut result = json!({
        "task_id": task.task_id,
        "logical_step": task.logical_step,
        "reason_units": task.reason_units,
        "input_refs": task.input_refs,
        "output_refs": task.output_contract.get("state_refs").cloned().unwrap_or_else(|| json!([])),
        "transition": {
            "transition_id": task.source_step.get("transition_id"),
            "source": task.source_step.get("source"),
            "target": task.source_step.get("target")
        },
        "input_state_version": state_version
    });
    if let Some(program) = &task.runtime_workload {
        let host = context
            .host
            .as_ref()
            .ok_or("CRR-RTH-001: runtime host is required for a computation workload")?;
        let root = context
            .resource_root
            .as_ref()
            .ok_or("CRR-RTH-002: resource root is required for a computation workload")?;
        let request = json!({
            "schema": "reasonscript-runtime-request/1.0",
            "request_id": format!("cluster-{}-{}", task.task_id, state_version),
            "operation": "execute",
            "program": program,
            "context": {
                "capabilities": {"filesystem_read": context.filesystem_read, "filesystem_write": context.filesystem_write},
                "limits": {}, "trace": {"enabled": true}, "resource_root": root,
                "numeric_mode": "compat-reference", "backend": context.backend, "transport_tensors": true,
            }
        });
        let mut child = Command::new(host)
            .arg("-")
            .current_dir(root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| format!("CRR-RTH-001: {error}"))?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or("CRR-RTH-001: runtime host stdin unavailable")?;
        stdin
            .write_all(
                serde_json::to_string(&request)
                    .map_err(|e| format!("CRR-RTH-001: {e}"))?
                    .as_bytes(),
            )
            .map_err(|error| format!("CRR-RTH-001: {error}"))?;
        drop(stdin);
        let output = child
            .wait_with_output()
            .map_err(|error| format!("CRR-RTH-001: {error}"))?;
        let runtime: Value = serde_json::from_slice(&output.stdout)
            .map_err(|error| format!("CRR-RTH-003: invalid runtime host response: {error}"))?;
        if !output.status.success() || runtime.get("ok") != Some(&Value::Bool(true)) {
            let diagnostic = runtime
                .get("diagnostics")
                .and_then(Value::as_array)
                .and_then(|items| items.first())
                .and_then(|item| item.get("code"))
                .and_then(Value::as_str)
                .unwrap_or("CRR-RTH-003");
            return Err(format!(
                "{diagnostic}: {}",
                runtime
                    .pointer("/diagnostics/0/message")
                    .and_then(Value::as_str)
                    .unwrap_or("runtime workload failed")
            ));
        }
        result["runtime"] = runtime;
    }
    Ok(result)
}
