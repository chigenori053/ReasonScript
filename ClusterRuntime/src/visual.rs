//! Bounded, deterministic runtime orchestration. The `visual` module name is retained for API compatibility.
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

pub const RUNTIME_SCHEMA: &str = "reasonscript-runtime-task/1.0";
pub const OUTPUT_SCHEMA: &str = "reasonscript-runtime-output/1.0";
fn task_schema() -> String {
    RUNTIME_SCHEMA.into()
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RuntimeTask {
    #[serde(default = "task_schema")]
    pub schema_version: String,
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
pub struct ClusterLimits {
    pub max_workers: usize,
    pub max_operations: usize,
    pub max_memory: usize,
    pub timeout_ms: u64,
    pub max_state_size: usize,
    pub local_threshold: usize,
}
impl Default for ClusterLimits {
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
pub type VisualLimits = ClusterLimits;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeWorkload {
    pub estimated_operations: usize,
    pub state_size: usize,
    pub parallel_units: usize,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SchedulingDecision {
    pub mode: String,
    pub workload: RuntimeWorkload,
    pub threshold: usize,
    pub reason: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TaskOutput {
    pub schema_version: String,
    pub task_id: String,
    pub runtime_type: String,
    pub status: String,
    pub output_state: Value,
    pub semantic_state: Value,
    pub provenance: Vec<String>,
    pub metrics: Value,
    pub observation: Option<VisualObservation>,
    pub geometry_state: Option<GeometryState>,
    pub trace: ReasonTrace,
}
pub type RuntimeOutput = TaskOutput;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VisualRun {
    pub status: String,
    pub decision: String,
    pub scheduling: SchedulingDecision,
    pub geometry_state: Option<GeometryState>,
    pub semantic_state: Value,
    pub task_outputs: Vec<TaskOutput>,
    pub operations: usize,
}

pub trait RuntimeAdapter: Sync {
    fn runtime_type(&self) -> &'static str;
    fn validate_task(&self, task: &RuntimeTask) -> Result<(), String>;
    fn estimate_workload(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> RuntimeWorkload;
    fn decompose(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> Vec<String>;
    fn execute(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> Result<TaskOutput, String>;
    fn canonicalize_output(&self, output: &mut TaskOutput) -> Result<(), String>;
}

#[derive(Default)]
pub struct RuntimeRegistry {
    adapters: BTreeMap<String, Box<dyn RuntimeAdapter>>,
}
impl RuntimeRegistry {
    pub fn register(&mut self, adapter: Box<dyn RuntimeAdapter>) -> Result<(), String> {
        let id = adapter.runtime_type();
        if id.is_empty() || self.adapters.contains_key(id) {
            return Err(format!("DCR-REG-001: duplicate or empty runtime {id}"));
        }
        self.adapters.insert(id.into(), adapter);
        Ok(())
    }
    pub fn get(&self, id: &str) -> Result<&dyn RuntimeAdapter, String> {
        self.adapters
            .get(id)
            .map(|adapter| adapter.as_ref())
            .ok_or_else(|| format!("UNSUPPORTED_RUNTIME: {id}"))
    }
}
pub fn default_registry() -> RuntimeRegistry {
    let mut registry = RuntimeRegistry::default();
    registry
        .register(Box::new(VisionRuntimeAdapter))
        .expect("unique VISION adapter");
    registry
        .register(Box::new(GeometryRuntimeAdapter))
        .expect("unique GEOMETRY adapter");
    registry
}

pub struct VisionRuntimeAdapter;
impl RuntimeAdapter for VisionRuntimeAdapter {
    fn runtime_type(&self) -> &'static str {
        "VISION"
    }
    fn validate_task(&self, task: &RuntimeTask) -> Result<(), String> {
        if task.goal != "EXTRACT_OBJECTS" {
            return Err("VIS-TASK-001: unsupported goal".into());
        }
        serde_json::from_value::<VisionObservation>(task.input_state.clone())
            .map(|_| ())
            .map_err(|e| format!("VIS-TASK-002: {e}"))
    }
    fn estimate_workload(&self, task: &RuntimeTask, _: &[TaskOutput]) -> RuntimeWorkload {
        let count = task.input_state["detections"]
            .as_array()
            .map_or(0, Vec::len);
        RuntimeWorkload {
            estimated_operations: count,
            state_size: size(&task.input_state).unwrap_or(usize::MAX),
            parallel_units: 1,
        }
    }
    fn decompose(&self, task: &RuntimeTask, _: &[TaskOutput]) -> Vec<String> {
        vec![task.task_id.clone()]
    }
    fn execute(&self, task: &RuntimeTask, _: &[TaskOutput]) -> Result<TaskOutput, String> {
        let source: VisionObservation = serde_json::from_value(task.input_state.clone())
            .map_err(|e| format!("VIS-TASK-002: {e}"))?;
        let observation = observe_spatial(&source).map_err(|e| e.to_string())?;
        let count = observation.objects.len();
        make_output(task, Some(observation), None, count)
    }
    fn canonicalize_output(&self, output: &mut TaskOutput) -> Result<(), String> {
        if let Some(obs) = &mut output.observation {
            obs.objects.sort_by(|a, b| a.object_id.cmp(&b.object_id));
        }
        finish_output(output)
    }
}

pub struct GeometryRuntimeAdapter;
fn geometry_input(task: &RuntimeTask, deps: &[TaskOutput]) -> Result<GeometryState, String> {
    if !task.input_state.is_null() {
        if let Ok(obs) = serde_json::from_value::<VisualObservation>(task.input_state.clone()) {
            return from_visual(&obs);
        }
        let mut state: GeometryState = serde_json::from_value(task.input_state.clone())
            .map_err(|e| format!("GEO-TASK-002: {e}"))?;
        canonicalize(&mut state)?;
        return Ok(state);
    }
    let mut inputs = vec![];
    for dep in deps {
        if let Some(obs) = &dep.observation {
            inputs.push(from_visual(obs)?);
        } else if let Some(state) = &dep.geometry_state {
            inputs.push(state.clone());
        }
    }
    merge(&inputs)
}
impl RuntimeAdapter for GeometryRuntimeAdapter {
    fn runtime_type(&self) -> &'static str {
        "GEOMETRY"
    }
    fn validate_task(&self, task: &RuntimeTask) -> Result<(), String> {
        if task.goal != "CALCULATE_SPATIAL_RELATIONS" {
            return Err("GEO-TASK-001: unsupported goal".into());
        }
        if !task.input_state.is_null() {
            geometry_input(task, &[])?;
        }
        Ok(())
    }
    fn estimate_workload(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> RuntimeWorkload {
        let count = if !task.input_state.is_null() {
            if let Some(objects) = task.input_state["objects"].as_array() {
                objects.len().saturating_mul(2)
            } else if let Some(primitives) = task.input_state["primitives"].as_array() {
                primitives.len()
            } else {
                task.input_state["detections"]
                    .as_array()
                    .map_or(0, |items| items.len().saturating_mul(2))
            }
        } else if deps.is_empty() {
            task.dependencies.len().saturating_mul(2)
        } else {
            deps.iter()
                .map(|o| {
                    o.observation
                        .as_ref()
                        .map_or(0, |v| v.objects.len().saturating_mul(2))
                        + o.geometry_state.as_ref().map_or(0, |v| v.primitives.len())
                })
                .sum()
        };
        RuntimeWorkload {
            estimated_operations: count.saturating_mul(count),
            state_size: size(&task.input_state).unwrap_or(usize::MAX),
            parallel_units: count.saturating_mul(count.saturating_sub(1)) / 2,
        }
    }
    fn decompose(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> Vec<String> {
        let mut ids = BTreeSet::new();
        if let Ok(state) = geometry_input(task, deps) {
            for primitive in state.primitives {
                ids.insert(primitive.geometry_id);
            }
        }
        let ids: Vec<_> = ids.into_iter().collect();
        let mut pairs = vec![];
        for (index, left) in ids.iter().enumerate() {
            for right in ids.iter().skip(index + 1) {
                pairs.push(format!("{}:pair:{left}:{right}", task.task_id));
            }
        }
        pairs
    }
    fn execute(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> Result<TaskOutput, String> {
        let mut state = geometry_input(task, deps)?;
        let count = state
            .primitives
            .len()
            .saturating_mul(state.primitives.len());
        derive_relations(&mut state, &Tolerance::default(), 100.0)?;
        make_output(task, None, Some(state), count)
    }
    fn canonicalize_output(&self, output: &mut TaskOutput) -> Result<(), String> {
        if let Some(state) = &mut output.geometry_state {
            canonicalize(state)?;
        }
        finish_output(output)
    }
}

fn size<T: Serialize + ?Sized>(value: &T) -> Result<usize, String> {
    serde_json::to_vec(value)
        .map(|v| v.len())
        .map_err(|e| e.to_string())
}
fn error(message: &str) -> String {
    format!("RESOURCE_LIMIT: {message}")
}
fn make_output(
    task: &RuntimeTask,
    observation: Option<VisualObservation>,
    geometry_state: Option<GeometryState>,
    operations: usize,
) -> Result<TaskOutput, String> {
    let trace = ReasonTrace {
        task_id: task.task_id.clone(),
        runtime: task.runtime_type.clone(),
        worker_id: format!("worker:{}:{}", task.runtime_type, task.task_id),
        input_hash: digest(&task.input_state)?,
        operations: vec![
            json!({"goal":task.goal,"operation_count":operations,"dependencies":task.dependencies,
            "worker_lifecycle":["CREATE","DISPATCH","EXECUTE","COLLECT","MERGE","TERMINATE"]}),
        ],
        output_hash: String::new(),
        provenance: vec![],
        status: "KNOWN".into(),
    };
    let mut output = TaskOutput {
        schema_version: OUTPUT_SCHEMA.into(),
        task_id: task.task_id.clone(),
        runtime_type: task.runtime_type.clone(),
        status: "COMPLETED".into(),
        output_state: Value::Null,
        semantic_state: Value::Null,
        provenance: task.provenance.clone(),
        metrics: json!({"operations":operations}),
        observation,
        geometry_state,
        trace,
    };
    finish_output(&mut output)?;
    Ok(output)
}
fn finish_output(output: &mut TaskOutput) -> Result<(), String> {
    output.output_state = if let Some(state) = &output.geometry_state {
        serde_json::to_value(state).map_err(|e| e.to_string())?
    } else if let Some(obs) = &output.observation {
        serde_json::to_value(obs).map_err(|e| e.to_string())?
    } else {
        Value::Null
    };
    output.semantic_state = output
        .geometry_state
        .as_ref()
        .map(mirp_projection)
        .unwrap_or(Value::Null);
    if let Some(obs) = &output.observation {
        output.provenance.extend(obs.provenance.clone());
    }
    if let Some(state) = &output.geometry_state {
        output.provenance.extend(state.provenance.clone());
    }
    output.provenance.sort();
    output.provenance.dedup();
    output.trace.provenance = output.provenance.clone();
    output.trace.output_hash = digest(&output.output_state)?;
    output.trace.status = if output
        .geometry_state
        .as_ref()
        .is_some_and(|s| !s.conflicts.is_empty())
    {
        "CONFLICT".into()
    } else if output
        .geometry_state
        .as_ref()
        .is_some_and(|s| !s.unknowns.is_empty())
    {
        "UNKNOWN".into()
    } else {
        "KNOWN".into()
    };
    output.status = if output.trace.status == "KNOWN" {
        "COMPLETED".into()
    } else {
        output.trace.status.clone()
    };
    Ok(())
}

/// Scheduling depends on canonical tasks and workload only. The worker count bounds execution,
/// while task identity, output order, and semantic trace remain independent of worker allocation.
pub fn run_runtime(
    tasks: &[RuntimeTask],
    limits: &ClusterLimits,
    registry: &RuntimeRegistry,
) -> Result<VisualRun, String> {
    if limits.max_workers == 0
        || limits.max_operations == 0
        || limits.max_memory == 0
        || limits.max_state_size == 0
        || limits.timeout_ms == 0
    {
        return Err(error("zero limit"));
    }
    if size(tasks)? > limits.max_memory {
        return Err(error("task memory budget exceeded"));
    }
    let started = Instant::now();
    let mut pending = BTreeMap::<String, RuntimeTask>::new();
    for task in tasks {
        if task.schema_version != RUNTIME_SCHEMA {
            return Err("DCR-TASK-001: unsupported schema_version".into());
        }
        if task.task_id.is_empty() || pending.insert(task.task_id.clone(), task.clone()).is_some() {
            return Err("VGR-TASK-002: duplicate or empty task identity".into());
        }
        registry.get(&task.runtime_type)?.validate_task(task)?;
        if task.dependencies.iter().collect::<BTreeSet<_>>().len() != task.dependencies.len() {
            return Err("VGR-TASK-003: duplicate dependency".into());
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
    let mut workload = RuntimeWorkload {
        estimated_operations: 0,
        state_size: 0,
        parallel_units: 0,
    };
    for task in pending.values() {
        let estimate = registry
            .get(&task.runtime_type)?
            .estimate_workload(task, &[]);
        workload.estimated_operations = workload
            .estimated_operations
            .saturating_add(estimate.estimated_operations);
        workload.state_size = workload.state_size.saturating_add(estimate.state_size);
        workload.parallel_units = workload
            .parallel_units
            .saturating_add(estimate.parallel_units.max(1));
    }
    let clustered = workload.estimated_operations > limits.local_threshold
        && workload.parallel_units > 1
        && limits.max_workers > 1;
    let decision = if clustered { "cluster" } else { "local" }.to_owned();
    let scheduling = SchedulingDecision {
        mode: decision.clone(),
        workload,
        threshold: limits.local_threshold,
        reason: if clustered {
            "workload_above_threshold_and_parallel_units"
        } else {
            "local_threshold_or_parallelism_limit"
        }
        .into(),
    };
    let mut outputs = BTreeMap::<String, TaskOutput>::new();
    let mut operations = 0usize;
    while !pending.is_empty() {
        if started.elapsed() > Duration::from_millis(limits.timeout_ms) {
            return Err(error("TIMEOUT"));
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
        let mut work = vec![];
        for task in &ready {
            let mut deps: Vec<_> = task
                .dependencies
                .iter()
                .map(|id| outputs[id].clone())
                .collect();
            deps.sort_by(|a, b| a.task_id.cmp(&b.task_id));
            let adapter = registry.get(&task.runtime_type)?;
            let estimate = adapter.estimate_workload(task, &deps);
            let units = adapter.decompose(task, &deps);
            if units.windows(2).any(|pair| pair[0] >= pair[1]) {
                return Err("DCR-ADAPTER-001: noncanonical decomposition".into());
            }
            if operations.saturating_add(estimate.estimated_operations) > limits.max_operations {
                return Err(error("operation budget exceeded"));
            }
            work.push((deps, estimate));
        }
        let completed: Vec<Result<TaskOutput, String>> = thread::scope(|scope| {
            let handles: Vec<_> = ready
                .iter()
                .zip(&work)
                .map(|(task, (deps, _))| {
                    let adapter = registry.get(&task.runtime_type).expect("validated adapter");
                    scope.spawn(move || adapter.execute(task, deps))
                })
                .collect();
            handles
                .into_iter()
                .map(|handle| {
                    handle
                        .join()
                        .unwrap_or_else(|_| Err("DCR-WORKER-001: worker panic".into()))
                })
                .collect()
        });
        for (task, item) in ready.iter().zip(completed) {
            let mut item = item?;
            registry
                .get(&task.runtime_type)?
                .canonicalize_output(&mut item)?;
            operations = operations
                .saturating_add(item.metrics["operations"].as_u64().unwrap_or(0) as usize);
            if operations > limits.max_operations {
                return Err(error("operation budget exceeded"));
            }
            if size(&item)? > limits.max_state_size {
                return Err(error("state size exceeded"));
            }
            pending.remove(&task.task_id);
            outputs.insert(task.task_id.clone(), item);
        }
    }
    if started.elapsed() > Duration::from_millis(limits.timeout_ms) {
        return Err(error("TIMEOUT"));
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
    let status = if state.as_ref().is_some_and(|s| !s.conflicts.is_empty()) {
        "CONFLICT"
    } else if state.as_ref().is_some_and(|s| !s.unknowns.is_empty()) {
        "UNKNOWN"
    } else {
        "COMPLETED"
    };
    let run = VisualRun {
        status: status.into(),
        decision,
        scheduling,
        geometry_state: state,
        semantic_state,
        task_outputs: outputs.into_values().collect(),
        operations,
    };
    if size(&run)? > limits.max_state_size {
        return Err(error("state size exceeded"));
    }
    if size(&run)? > limits.max_memory {
        return Err(error("memory budget exceeded"));
    }
    Ok(run)
}
pub fn run_visual(tasks: &[RuntimeTask], limits: &VisualLimits) -> Result<VisualRun, String> {
    run_runtime(tasks, limits, &default_registry())
}
