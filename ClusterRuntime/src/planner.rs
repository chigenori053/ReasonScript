use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::{
    canonical::checksum,
    diagnostics::{sort, Diagnostic},
};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ReasonTask {
    pub task_id: String,
    pub reason_units: Vec<String>,
    pub input_refs: Vec<String>,
    pub output_contract: Value,
    pub dependency_ids: Vec<String>,
    pub execution_policy: Value,
    pub retry_policy: Value,
    pub resource_hint: Value,
    pub partition_id: String,
    pub logical_step: usize,
    pub dependency_depth: usize,
    pub assigned_worker: String,
    pub source_step: Value,
    /// Computation IR assigned to this logical ReasonUnit.  It is optional
    /// so the cluster remains compatible with pre-runtime artifact bundles.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub runtime_workload: Option<Value>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Partition {
    pub partition_id: String,
    pub logical_step: usize,
    pub task_ids: Vec<String>,
    pub assigned_worker: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Barrier {
    pub logical_step: usize,
    pub required_task_ids: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ClusterPlan {
    pub schema_version: String,
    pub plan_id: String,
    pub source_plan_hash: String,
    pub sync_policy: String,
    pub tasks: Vec<ReasonTask>,
    pub partitions: Vec<Partition>,
    pub barriers: Vec<Barrier>,
    pub diagnostics: Vec<Diagnostic>,
    pub valid: bool,
}

pub fn build_cluster_plan(
    execution_plan: &Value,
    reason_ir: &Value,
    worker_ids: &[String],
    sync_policy: &str,
) -> ClusterPlan {
    let source_hash = checksum(execution_plan).unwrap_or_else(|_| "sha256:invalid".into());
    let prefix = source_hash.strip_prefix("sha256:").unwrap_or(&source_hash);
    let plan_id = format!("cluster_plan_{}", &prefix[..prefix.len().min(16)]);
    let steps = execution_plan
        .get("selected_steps")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut diagnostics = Vec::new();
    if steps.is_empty() {
        diagnostics.push(Diagnostic::error(
            "CRR-PLN-001",
            "ExecutionPlan cannot be partitioned",
            "execution_plan.selected_steps",
        ));
    }
    let transitions: HashMap<_, _> = reason_ir
        .get("transitions")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|t| Some((t.get("transition_id")?.as_str()?.to_string(), t)))
        .collect();
    let mut producers = HashMap::<String, String>::new();
    let mut writes = BTreeMap::<String, Vec<(String, String)>>::new();
    let fallback_worker = "worker-0".to_string();
    let workers = if worker_ids.is_empty() {
        vec![fallback_worker]
    } else {
        worker_ids.to_vec()
    };
    let mut tasks = Vec::new();
    for (index, step) in steps.iter().enumerate() {
        let task_id = format!("task_{:04}", index + 1);
        let transition_id = step
            .get("transition_id")
            .and_then(Value::as_str)
            .unwrap_or("unknown");
        let transition = transitions.get(transition_id).copied();
        let effect = transition
            .and_then(|v| v.get("effect"))
            .unwrap_or(&Value::Null);
        let policy = transition
            .and_then(|v| v.get("cluster_policy"))
            .unwrap_or(&Value::Null);
        let source = step
            .get("source")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let target = step
            .get("target")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let mut inputs = BTreeSet::from([source]);
        for input in effect
            .get("inputs")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
        {
            inputs.insert(input.to_string());
        }
        let dependencies: BTreeSet<_> = inputs
            .iter()
            .filter_map(|input| producers.get(input).cloned())
            .collect();
        let deterministic = policy
            .get("deterministic")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        if !deterministic {
            diagnostics.push(Diagnostic::error(
                "CRR-PLN-005",
                "Non-deterministic ReasonUnit",
                &task_id,
            ));
        }
        let merge_policy = policy
            .get("merge_policy")
            .and_then(Value::as_str)
            .unwrap_or("replace")
            .to_string();
        let write_set: Vec<String> = policy
            .get("state_access")
            .and_then(|v| v.get("write"))
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_else(|| vec![target.clone()]);
        for state in write_set {
            writes
                .entry(state)
                .or_default()
                .push((task_id.clone(), merge_policy.clone()));
        }
        let partition_id = format!(
            "partition_{}_{:04}",
            &prefix[..prefix.len().min(12)],
            index + 1
        );
        tasks.push(ReasonTask {
            task_id: task_id.clone(), reason_units: vec![transition_id.into()], input_refs: inputs.into_iter().collect(),
            output_contract: json!({"state_refs": if target.is_empty() { vec![] } else { vec![target.clone()] }, "merge_policy": merge_policy}),
            dependency_ids: dependencies.into_iter().collect(), execution_policy: json!({"deterministic": deterministic, "retriable": policy.get("retriable").and_then(Value::as_bool).unwrap_or(true), "atomic": policy.get("atomic").and_then(Value::as_bool).unwrap_or(false)}),
            retry_policy: json!({"max_retries": 1}), resource_hint: policy.get("resource_hint").cloned().unwrap_or_else(|| json!({"cpu_weight": 1, "memory_bytes": 0})),
            partition_id, logical_step: 0, dependency_depth: 0, assigned_worker: workers[index % workers.len()].clone(), source_step: step.clone(),
            runtime_workload: None,
        });
        if !target.is_empty() {
            producers.insert(target, task_id);
        }
    }
    assign_depths(&mut tasks, &mut diagnostics);
    for (state, owners) in writes {
        let ids: HashSet<_> = owners.iter().map(|(id, _)| id).collect();
        let merge_safe = owners.iter().all(|(_, policy)| {
            matches!(
                policy.as_str(),
                "append" | "set_union" | "ordered_merge" | "numeric_reduce"
            )
        });
        if ids.len() > 1 && !merge_safe {
            diagnostics.push(Diagnostic::error(
                "CRR-PLN-006",
                format!("Non-commutative writes target {state}"),
                state,
            ));
        }
    }
    tasks.sort_by_key(|t| {
        (
            t.logical_step,
            t.dependency_depth,
            t.partition_id.clone(),
            t.task_id.clone(),
            t.assigned_worker.clone(),
        )
    });
    let partitions = tasks
        .iter()
        .map(|task| Partition {
            partition_id: task.partition_id.clone(),
            logical_step: task.logical_step,
            task_ids: vec![task.task_id.clone()],
            assigned_worker: task.assigned_worker.clone(),
        })
        .collect();
    let mut grouped = BTreeMap::<usize, Vec<String>>::new();
    for task in &tasks {
        grouped
            .entry(task.logical_step)
            .or_default()
            .push(task.task_id.clone());
    }
    let barriers = if sync_policy == "barrier" {
        grouped
            .into_iter()
            .map(|(logical_step, mut ids)| {
                ids.sort();
                Barrier {
                    logical_step,
                    required_task_ids: ids,
                }
            })
            .collect()
    } else {
        Vec::new()
    };
    sort(&mut diagnostics);
    ClusterPlan {
        schema_version: "reasonscript-cluster-plan/0.1".into(),
        plan_id,
        source_plan_hash: source_hash,
        sync_policy: sync_policy.into(),
        tasks,
        partitions,
        barriers,
        valid: !diagnostics.iter().any(|d| d.severity == "error"),
        diagnostics,
    }
}

/// Assign a prefix of the computation program to each calculation-backed
/// transition.  A prefix preserves calculation dependencies (`B` can refer to
/// the result of `A`) while ensuring the actual target calculation executes in
/// the worker which owns that ReasonUnit.
pub fn attach_runtime_workloads(
    plan: &mut ClusterPlan,
    reason_ir: &Value,
    computation_ir: Option<&Value>,
) {
    let Some(program) = computation_ir else {
        return;
    };
    let Some(calculations) = program.get("calculations").and_then(Value::as_array) else {
        return;
    };
    let Some(functions) = program.get("functions").and_then(Value::as_array) else {
        return;
    };
    for task in &mut plan.tasks {
        let transition_id = task
            .source_step
            .get("transition_id")
            .and_then(Value::as_str);
        let calculation = reason_ir
            .get("transitions")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .find(|transition| {
                transition.get("transition_id").and_then(Value::as_str) == transition_id
            })
            .and_then(|transition| transition.pointer("/effect/calculation"))
            .and_then(Value::as_str);
        let is_result_transition = reason_ir
            .get("transitions")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .find(|transition| {
                transition.get("transition_id").and_then(Value::as_str) == transition_id
            })
            .and_then(|transition| transition.pointer("/effect/target"))
            .and_then(Value::as_str)
            == Some("result");
        if !is_result_transition {
            continue;
        }
        let Some(calculation) = calculation else {
            continue;
        };
        let Some(position) = calculations
            .iter()
            .position(|item| item.as_str() == Some(calculation))
        else {
            continue;
        };
        let selected: Vec<Value> = calculations[..=position].to_vec();
        let selected_functions: Vec<Value> = functions
            .iter()
            .filter(|function| {
                function
                    .get("id")
                    .and_then(Value::as_str)
                    .is_some_and(|id| selected.iter().any(|name| name.as_str() == Some(id)))
            })
            .cloned()
            .collect();
        if selected_functions.len() == selected.len() {
            let mut workload = program.clone();
            workload["calculations"] = Value::Array(selected);
            workload["functions"] = Value::Array(selected_functions);
            task.runtime_workload = Some(workload);
        }
    }
}

fn assign_depths(tasks: &mut [ReasonTask], diagnostics: &mut Vec<Diagnostic>) {
    let by_id: HashMap<_, _> = tasks
        .iter()
        .enumerate()
        .map(|(i, task)| (task.task_id.clone(), i))
        .collect();
    let mut remaining: HashSet<_> = by_id.keys().cloned().collect();
    let mut resolved = HashSet::new();
    while !remaining.is_empty() {
        let mut ready: Vec<_> = remaining
            .iter()
            .filter(|id| {
                tasks[by_id[*id]]
                    .dependency_ids
                    .iter()
                    .all(|dep| resolved.contains(dep))
            })
            .cloned()
            .collect();
        ready.sort();
        if ready.is_empty() {
            diagnostics.push(Diagnostic::error(
                "CRR-PLN-002",
                "Cyclic task dependency",
                "tasks",
            ));
            return;
        }
        for id in ready {
            let index = by_id[&id];
            let depth = tasks[index]
                .dependency_ids
                .iter()
                .filter_map(|dep| by_id.get(dep).map(|i| tasks[*i].dependency_depth + 1))
                .max()
                .unwrap_or(0);
            tasks[index].dependency_depth = depth;
            tasks[index].logical_step = depth;
            remaining.remove(&id);
            resolved.insert(id);
        }
    }
}
