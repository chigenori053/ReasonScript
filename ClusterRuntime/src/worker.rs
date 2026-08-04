use serde_json::{json, Value};

use crate::planner::ReasonTask;

pub fn execute(task: &ReasonTask, state_version: usize) -> Value {
    json!({
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
    })
}
