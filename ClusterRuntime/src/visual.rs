//! Bounded Vision and Geometry task execution with deterministic state merge.
use reasonscript_geometry_runtime::{
    canonicalize, derive_relations, digest, from_visual, merge, mirp_projection, GeometryState,
    ReasonTrace, Tolerance,
};
use reasonscript_vision_runtime::{
    spatial::{observe_spatial, VisualObservation},
    VisionObservation,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    thread,
    time::{Duration, Instant},
};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RuntimeTask {
    pub task_id: String,
    pub runtime_type: String,
    pub input_state: Value,
    pub goal: String,
    #[serde(default)]
    pub resource_hint: Value,
    #[serde(default)]
    pub dependencies: Vec<String>,
    #[serde(default)]
    pub provenance: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct VisualLimits {
    pub max_workers: usize,
    pub max_operations: usize,
    pub max_memory: usize,
    pub timeout_ms: u64,
    pub max_state_size: usize,
    pub local_threshold: usize,
}
impl Default for VisualLimits {
    fn default() -> Self {
        Self {
            max_workers: 4,
            max_operations: 10_000,
            max_memory: 64 * 1024 * 1024,
            timeout_ms: 30_000,
            max_state_size: 16 * 1024 * 1024,
            local_threshold: 2,
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TaskOutput {
    pub task_id: String,
    pub runtime_type: String,
    pub observation: Option<VisualObservation>,
    pub geometry_state: Option<GeometryState>,
    pub trace: ReasonTrace,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VisualRun {
    pub status: String,
    pub decision: String,
    pub geometry_state: Option<GeometryState>,
    pub semantic_state: Value,
    pub task_outputs: Vec<TaskOutput>,
    pub operations: usize,
}
fn error(message: &str) -> String {
    format!("RESOURCE_LIMIT: {message}")
}
fn size<T: Serialize>(value: &T) -> Result<usize, String> {
    serde_json::to_vec(value)
        .map(|v| v.len())
        .map_err(|e| e.to_string())
}
fn execute(task: &RuntimeTask, deps: &[TaskOutput], worker: &str) -> Result<TaskOutput, String> {
    let input_hash = digest(&task.input_state)?;
    let (observation, geometry_state, operations) = match task.runtime_type.as_str() {
        "VISION" => {
            if task.goal != "EXTRACT_OBJECTS" {
                return Err("VIS-TASK-001: unsupported goal".into());
            }
            let source: VisionObservation = serde_json::from_value(task.input_state.clone())
                .map_err(|e| format!("VIS-TASK-002: {e}"))?;
            let observation = observe_spatial(&source).map_err(|e| e.to_string())?;
            let count = observation.objects.len();
            (Some(observation), None, count)
        }
        "GEOMETRY" => {
            if task.goal != "CALCULATE_SPATIAL_RELATIONS" {
                return Err("GEO-TASK-001: unsupported goal".into());
            }
            let mut state = if !task.input_state.is_null() {
                if let Ok(obs) =
                    serde_json::from_value::<VisualObservation>(task.input_state.clone())
                {
                    from_visual(&obs)?
                } else {
                    let mut state: GeometryState = serde_json::from_value(task.input_state.clone())
                        .map_err(|e| format!("GEO-TASK-002: {e}"))?;
                    canonicalize(&mut state)?;
                    state
                }
            } else {
                let mut inputs = vec![];
                for dep in deps {
                    if let Some(obs) = &dep.observation {
                        inputs.push(from_visual(obs)?)
                    } else if let Some(state) = &dep.geometry_state {
                        inputs.push(state.clone())
                    }
                }
                merge(&inputs)?
            };
            let count = state
                .primitives
                .len()
                .saturating_mul(state.primitives.len());
            derive_relations(&mut state, &Tolerance::default(), 100.0)?;
            (None, Some(state), count)
        }
        _ => return Err("VGR-TASK-001: runtime_type must be VISION or GEOMETRY".into()),
    };
    let output_hash = digest(&(observation.as_ref(), geometry_state.as_ref()))?;
    let mut provenance = task.provenance.clone();
    if let Some(obs) = &observation {
        provenance.extend(obs.provenance.clone())
    }
    if let Some(state) = &geometry_state {
        provenance.extend(state.provenance.clone())
    }
    provenance.sort();
    provenance.dedup();
    let trace = ReasonTrace {
        task_id: task.task_id.clone(),
        runtime: task.runtime_type.clone(),
        worker_id: worker.into(),
        input_hash,
        operations: vec![
            json!({"goal":task.goal,"operation_count":operations,"dependencies":task.dependencies}),
        ],
        output_hash,
        provenance,
        status: "KNOWN".into(),
    };
    Ok(TaskOutput {
        task_id: task.task_id.clone(),
        runtime_type: task.runtime_type.clone(),
        observation,
        geometry_state,
        trace,
    })
}
/// A sorted wave is dispatched concurrently only when the declared workload exceeds the local threshold.
/// Each wave joins before dependent work starts; every merge is by stable task and geometry identity.
pub fn run_visual(tasks: &[RuntimeTask], limits: &VisualLimits) -> Result<VisualRun, String> {
    if limits.max_workers == 0
        || limits.max_operations == 0
        || limits.max_memory == 0
        || limits.max_state_size == 0
        || limits.timeout_ms == 0
    {
        return Err(error("zero limit"));
    }
    if tasks.len() > limits.max_operations || size(&tasks)? > limits.max_memory {
        return Err(error("task or memory budget exceeded"));
    }
    let started = Instant::now();
    let mut pending: BTreeMap<String, RuntimeTask> = BTreeMap::new();
    for task in tasks {
        if task.task_id.is_empty() || pending.insert(task.task_id.clone(), task.clone()).is_some() {
            return Err("VGR-TASK-002: duplicate or empty task identity".into());
        }
    }
    let ids: BTreeSet<_> = pending.keys().cloned().collect();
    for task in pending.values() {
        if task
            .dependencies
            .iter()
            .any(|id| !ids.contains(id) || id == &task.task_id)
        {
            return Err("VGR-TASK-003: missing or self dependency".into());
        }
    }
    let workload: usize = pending
        .values()
        .map(|t| {
            t.resource_hint["estimated_operations"]
                .as_u64()
                .unwrap_or(1) as usize
        })
        .sum();
    let clustered = workload > limits.local_threshold && limits.max_workers > 1;
    let decision = if clustered { "cluster" } else { "local" }.to_owned();
    let mut outputs = BTreeMap::<String, TaskOutput>::new();
    let mut operations = 0usize;
    while !pending.is_empty() {
        if started.elapsed() > Duration::from_millis(limits.timeout_ms) {
            return Err(error("timeout"));
        }
        let ready: Vec<_> = pending
            .values()
            .filter(|t| t.dependencies.iter().all(|id| outputs.contains_key(id)))
            .take(if clustered { limits.max_workers } else { 1 })
            .cloned()
            .collect();
        if ready.is_empty() {
            return Err("VGR-TASK-004: dependency cycle".into());
        }
        let estimated: usize = ready
            .iter()
            .map(|task| {
                if task.runtime_type == "VISION" {
                    task.input_state["detections"]
                        .as_array()
                        .map_or(0, Vec::len)
                } else {
                    let count = if task.input_state.is_null() {
                        task.dependencies
                            .iter()
                            .map(|id| {
                                let output = &outputs[id];
                                output
                                    .observation
                                    .as_ref()
                                    .map_or(0, |o| o.objects.len().saturating_mul(2))
                                    + output
                                        .geometry_state
                                        .as_ref()
                                        .map_or(0, |s| s.primitives.len())
                            })
                            .sum::<usize>()
                    } else if let Some(objects) = task.input_state["objects"].as_array() {
                        objects.len().saturating_mul(2)
                    } else {
                        task.input_state["primitives"]
                            .as_array()
                            .map_or(0, Vec::len)
                    };
                    count.saturating_mul(count)
                }
            })
            .fold(0usize, usize::saturating_add);
        if operations.saturating_add(estimated) > limits.max_operations {
            return Err(error("operation budget exceeded"));
        }
        let mut completed = vec![];
        thread::scope(|scope| {
            let handles: Vec<_> = ready
                .iter()
                .enumerate()
                .map(|(i, task)| {
                    let deps: Vec<_> = task
                        .dependencies
                        .iter()
                        .map(|id| outputs[id].clone())
                        .collect();
                    let worker = if clustered {
                        format!("visual-worker-{i}")
                    } else {
                        "local".into()
                    };
                    scope.spawn(move || execute(task, &deps, &worker))
                })
                .collect();
            for handle in handles {
                completed.push(
                    handle
                        .join()
                        .map_err(|_| "VGR-TASK-005: worker panic".to_owned())?,
                )
            }
            Ok::<(), String>(())
        })?;
        for (task, item) in ready.iter().zip(completed) {
            let mut item = item?;
            operations = operations.saturating_add(
                item.trace.operations[0]["operation_count"]
                    .as_u64()
                    .unwrap_or(0) as usize,
            );
            if operations > limits.max_operations {
                return Err(error("operation budget exceeded"));
            }
            item.trace
                .operations
                .push(json!({"dispatch_decision":decision,"estimated_workload":workload}));
            item.trace
                .operations
                .push(json!({"worker_lifecycle":["spawn","dispatch","collect","terminate"]}));
            if size(&item)? > limits.max_state_size {
                return Err(error("state size exceeded"));
            }
            pending.remove(&task.task_id);
            outputs.insert(task.task_id.clone(), item);
        }
    }
    if started.elapsed() > Duration::from_millis(limits.timeout_ms) {
        return Err(error("timeout"));
    }
    let states: Vec<_> = outputs
        .values()
        .filter_map(|o| o.geometry_state.clone())
        .collect();
    let state = if states.is_empty() {
        None
    } else {
        Some(merge(&states)?)
    };
    let semantic_state = state.as_ref().map(mirp_projection).unwrap_or(Value::Null);
    if state
        .as_ref()
        .is_some_and(|state| size(state).unwrap_or(usize::MAX) > limits.max_state_size)
    {
        return Err(error("state size exceeded"));
    }
    let task_outputs = outputs.into_values().collect();
    let run = VisualRun {
        status: "COMPLETED".into(),
        decision,
        geometry_state: state,
        semantic_state,
        task_outputs,
        operations,
    };
    if size(&run)? > limits.max_memory {
        return Err(error("memory budget exceeded"));
    }
    Ok(run)
}
