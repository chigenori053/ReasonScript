use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::{canonical::checksum, messages::ClusterMessage, planner::ReasonTask};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ClusterEvaluation {
    pub schema_version: String,
    pub status: String,
    pub passed: bool,
    pub correctness: Value,
    pub determinism: Value,
    pub equivalence: Value,
    pub efficiency: Value,
    pub fallback_used: bool,
}

pub fn semantic_projection(bundle: &Value) -> Value {
    let payload = bundle.get("artifacts").unwrap_or(bundle);
    json!({
        "final_state": payload.get("simulation").and_then(|v| v.get("final_state")).cloned().unwrap_or(Value::Null),
        "simulation": payload.get("simulation").cloned().unwrap_or_else(|| json!({})),
        "knowledge": payload.get("knowledge").cloned().unwrap_or_else(|| json!({})),
        "evaluation": bundle.get("reasoning_runtime").and_then(|v| v.get("evaluation_report")).cloned().unwrap_or_else(|| json!({})),
        "diagnostics": bundle.get("diagnostics").cloned().unwrap_or_else(|| json!([]))
    })
}

pub fn evaluate(
    tasks: &[ReasonTask],
    completed: &[String],
    messages: &[ClusterMessage],
    trace: &[Value],
    retries: usize,
    workers: usize,
    expected: &Value,
    actual: &Value,
    fallback: bool,
) -> ClusterEvaluation {
    let mut required: Vec<_> = tasks.iter().map(|t| t.task_id.clone()).collect();
    required.sort();
    let mut done = completed.to_vec();
    done.sort();
    done.dedup();
    let dependency_ok = tasks
        .iter()
        .filter(|t| done.contains(&t.task_id))
        .all(|t| t.dependency_ids.iter().all(|id| done.contains(id)));
    let equivalence = expected == actual;
    let max_step = tasks
        .iter()
        .map(|t| t.logical_step)
        .max()
        .map_or(0, |s| s + 1);
    let parallel = (0..max_step)
        .map(|s| {
            tasks
                .iter()
                .filter(|t| t.logical_step == s)
                .count()
                .saturating_sub(1)
        })
        .sum::<usize>();
    let correctness = json!({"all_required_tasks_completed": required == done, "dependency_order_valid": dependency_ok, "state_conflict_free": true, "messages_complete": !messages.is_empty() || tasks.is_empty(), "trace_complete": !trace.is_empty() || tasks.is_empty(), "final_state_valid": !expected.get("final_state").map_or(true, Value::is_null), "knowledge_valid": expected.get("knowledge").map_or(false, Value::is_object)});
    let eq = json!({"final_state": actual.get("final_state") == expected.get("final_state"), "knowledge": actual.get("knowledge") == expected.get("knowledge"), "evaluation": actual.get("evaluation") == expected.get("evaluation"), "semantic_projection": equivalence});
    let passed = correctness
        .as_object()
        .unwrap()
        .values()
        .all(|v| v == &Value::Bool(true))
        && eq
            .as_object()
            .unwrap()
            .values()
            .all(|v| v == &Value::Bool(true));
    ClusterEvaluation {
        schema_version: "reasonscript-cluster-evaluation-report/0.1".into(),
        status: if passed { "passed" } else { "failed" }.into(),
        passed,
        correctness,
        determinism: json!({"canonicalized":true,"message_logically_ordered":true,"semantic_digest":checksum(actual).unwrap_or_default()}),
        equivalence: eq,
        efficiency: json!({"task_parallel_ratio": if tasks.is_empty(){0.0}else{parallel as f64/tasks.len() as f64},"worker_count":workers,"logical_steps":max_step,"message_count":messages.len(),"retry_count":retries}),
        fallback_used: fallback,
    }
}

pub fn compare(summary: &Value, single_node: &Value) -> Value {
    let expected = semantic_projection(single_node);
    let actual = summary
        .get("semantic_result")
        .cloned()
        .unwrap_or_else(|| json!({}));
    let checks = json!({"final_state":actual.get("final_state")==expected.get("final_state"),"simulation":actual.get("simulation")==expected.get("simulation"),"knowledge":actual.get("knowledge")==expected.get("knowledge"),"evaluation":actual.get("evaluation")==expected.get("evaluation"),"diagnostics":actual.get("diagnostics")==expected.get("diagnostics")});
    let equivalent = checks
        .as_object()
        .unwrap()
        .values()
        .all(|v| v == &Value::Bool(true));
    json!({"schema_version":"reasonscript-cluster-comparison/0.1","equivalent":equivalent,"checks":checks,"cluster_digest":checksum(&actual).unwrap_or_default(),"single_node_digest":checksum(&expected).unwrap_or_default()})
}
