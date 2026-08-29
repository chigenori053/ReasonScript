use std::{
    collections::{BTreeMap, BTreeSet, HashMap, HashSet},
    io::Write,
    path::PathBuf,
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::{
    artifacts::write_artifacts,
    config::ClusterConfig,
    diagnostics::{sort, Diagnostic},
    evaluator::{evaluate, semantic_projection},
    messages::{validate_stream, ClusterMessage},
    planner::{attach_runtime_workloads, build_cluster_plan, ClusterPlan, ReasonTask},
    state::StateSnapshot,
    worker::{self, RuntimeContext},
};

#[derive(Clone, Debug, Default)]
pub struct RunOptions {
    pub artifacts_dir: Option<PathBuf>,
    pub runtime: RuntimeContext,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ClusterRun {
    pub summary: Value,
    pub documents: BTreeMap<String, Value>,
}

struct MessageLog {
    run_id: String,
    items: Vec<ClusterMessage>,
    sequences: HashMap<(String, String), usize>,
}

impl MessageLog {
    fn new(run_id: &str) -> Self {
        Self {
            run_id: run_id.into(),
            items: Vec::new(),
            sequences: HashMap::new(),
        }
    }
    fn send(
        &mut self,
        sender: &str,
        receiver: &str,
        message_type: &str,
        logical_step: usize,
        payload: Value,
    ) -> Result<(), String> {
        let route = (sender.to_string(), receiver.to_string());
        let sequence = self.sequences.entry(route).or_insert(0);
        *sequence += 1;
        let id = format!("msg_{:06}", self.items.len() + 1);
        self.items.push(
            ClusterMessage::new(
                id,
                &self.run_id,
                logical_step,
                *sequence,
                sender,
                receiver,
                message_type,
                payload,
            )
            .map_err(|e| e.to_string())?,
        );
        Ok(())
    }
}

pub fn run_cluster(
    bundle: &Value,
    config: &ClusterConfig,
    options: &RunOptions,
) -> Result<ClusterRun, String> {
    let payload = bundle.get("artifacts").unwrap_or(bundle);
    let execution_plan = payload
        .get("execution_plan")
        .cloned()
        .unwrap_or(Value::Null);
    let reason_ir = payload.get("reason_ir").cloned().unwrap_or(Value::Null);
    let configured_workers: Vec<_> = config.workers.iter().map(|w| w.node_id.clone()).collect();
    let planning_workers = if configured_workers.is_empty() {
        vec!["single-node-fallback".into()]
    } else {
        configured_workers.clone()
    };
    let mut plan = build_cluster_plan(
        &execution_plan,
        &reason_ir,
        &planning_workers,
        &config.execution.sync_policy,
    );
    attach_runtime_workloads(&mut plan, &reason_ir, payload.get("computation_ir"));
    let run_id = format!(
        "cluster_run_{}",
        plan.plan_id.trim_start_matches("cluster_plan_")
    );
    let mut diagnostics = config.validate();
    diagnostics.extend(plan.diagnostics.clone());
    sort(&mut diagnostics);
    let has_fatal_config = diagnostics
        .iter()
        .any(|d| d.code.starts_with("CRR-CFG") && d.code != "CRR-CFG-005");
    let fallback = configured_workers.is_empty()
        && config.execution.fallback == "single_node"
        && !has_fatal_config;
    if fallback {
        for item in &mut diagnostics {
            if item.code == "CRR-CFG-005" {
                item.severity = "warning".into();
                item.message = "Insufficient workers; single-node fallback selected".into();
            }
        }
    }
    if !plan.valid || has_fatal_config || (!config.validate().is_empty() && !fallback) {
        return finish_failed(bundle, config, &plan, &run_id, diagnostics, options);
    }
    let workers = if fallback {
        vec!["single-node-fallback".into()]
    } else {
        configured_workers
    };
    if plan.tasks.len() > config.limits.max_tasks {
        diagnostics.push(Diagnostic::error(
            "CRR-RUN-002",
            "Task count exceeds max_tasks",
            "tasks",
        ));
        return finish_failed(bundle, config, &plan, &run_id, diagnostics, options);
    }
    let coordinator = &config.coordinator.node_id;
    let mut log = MessageLog::new(&run_id);
    let mut worker_states: BTreeMap<String, Value> = workers
        .iter()
        .map(|id| (id.clone(), json!({"status":"ready","completed_tasks":[]})))
        .collect();
    for worker in &workers {
        log.send(
            worker,
            coordinator,
            "worker_register",
            0,
            json!({"capacity":1}),
        )?;
        log.send(coordinator, worker, "worker_ready", 0, json!({}))?;
        log.send(
            worker,
            coordinator,
            "heartbeat",
            0,
            json!({"status":"ready"}),
        )?;
    }
    let mut task_states: HashMap<String, &str> = plan
        .tasks
        .iter()
        .map(|t| (t.task_id.clone(), "pending"))
        .collect();
    let mut completed = Vec::new();
    let mut committed = HashSet::new();
    let mut trace = Vec::new();
    let mut runtime_outputs = Vec::new();
    let mut snapshots = Vec::new();
    let mut retries = 0usize;
    let mut state_version = 0usize;
    let mut grouped = BTreeMap::<usize, Vec<&ReasonTask>>::new();
    for task in &plan.tasks {
        grouped.entry(task.logical_step).or_default().push(task);
    }
    for (logical_step, mut tasks) in grouped {
        if logical_step >= config.limits.max_logical_steps {
            diagnostics.push(Diagnostic::error(
                "CRR-RUN-005",
                "Logical step limit exceeded",
                logical_step.to_string(),
            ));
            break;
        }
        tasks.sort_by_key(|t| (&t.partition_id, &t.task_id));
        let mut assigned = Vec::new();
        let mut executable = Vec::new();
        for (index, task) in tasks.iter().enumerate() {
            transition(&mut task_states, &task.task_id, "ready", &mut diagnostics);
            let mut worker_id = workers[index % workers.len()].clone();
            transition(
                &mut task_states,
                &task.task_id,
                "assigned",
                &mut diagnostics,
            );
            log.send(
                coordinator,
                &worker_id,
                "task_assign",
                logical_step,
                json!({"task_id":task.task_id,"attempt":1,"state_version":state_version}),
            )?;
            transition(&mut task_states, &task.task_id, "running", &mut diagnostics);
            log.send(
                &worker_id,
                coordinator,
                "task_start",
                logical_step,
                json!({"task_id":task.task_id,"attempt":1}),
            )?;
            trace.push(json!({"event":"task_start","logical_step":logical_step,"task_id":task.task_id,"worker_id":worker_id,"attempt":1}));
            let should_fail = config
                .testing
                .as_ref()
                .and_then(|t| t.fail_task_once.as_ref())
                == Some(&task.task_id);
            if should_fail {
                transition(&mut task_states, &task.task_id, "failed", &mut diagnostics);
                log.send(
                    &worker_id,
                    coordinator,
                    "task_failure",
                    logical_step,
                    json!({"task_id":task.task_id,"attempt":1,"failure":"worker_unavailable"}),
                )?;
                worker_states.insert(
                    worker_id.clone(),
                    json!({"status":"unavailable","completed_tasks":[]}),
                );
                retries += 1;
                if retries > config.execution.max_retries {
                    diagnostics.push(Diagnostic::error(
                        "CRR-RUN-004",
                        "Worker retry limit exceeded",
                        &task.task_id,
                    ));
                    continue;
                }
                worker_id = workers[(index + 1) % workers.len()].clone();
                transition(
                    &mut task_states,
                    &task.task_id,
                    "assigned",
                    &mut diagnostics,
                );
                log.send(
                    coordinator,
                    &worker_id,
                    "task_assign",
                    logical_step,
                    json!({"task_id":task.task_id,"attempt":2,"state_version":state_version}),
                )?;
                transition(&mut task_states, &task.task_id, "running", &mut diagnostics);
                log.send(
                    &worker_id,
                    coordinator,
                    "task_start",
                    logical_step,
                    json!({"task_id":task.task_id,"attempt":2}),
                )?;
                trace.push(json!({"event":"task_retry","logical_step":logical_step,"task_id":task.task_id,"worker_id":worker_id,"attempt":2}));
            }
            assigned.push(worker_id);
            executable.push((*task).clone());
        }
        let results = if config.mode == "local_process" && !fallback {
            execute_local_processes(
                &executable,
                state_version,
                config.limits.task_timeout_ms,
                &options.runtime,
            )?
        } else {
            executable
                .iter()
                .map(|task| worker::execute(task, state_version, &options.runtime))
                .collect::<Result<Vec<_>, _>>()?
        };
        for ((task, result), worker_id) in executable.iter().zip(results).zip(assigned.iter()) {
            if !committed.insert(task.task_id.clone()) {
                diagnostics.push(Diagnostic::error(
                    "CRR-RUN-007",
                    "Duplicate task result",
                    &task.task_id,
                ));
                continue;
            }
            let attempt = if config
                .testing
                .as_ref()
                .and_then(|t| t.fail_task_once.as_ref())
                == Some(&task.task_id)
            {
                2
            } else {
                1
            };
            log.send(worker_id, coordinator, "task_result", logical_step, json!({"task_id":task.task_id,"attempt":attempt,"state_version":state_version,"result":result}))?;
            completed.push(task.task_id.clone());
            transition(
                &mut task_states,
                &task.task_id,
                "completed",
                &mut diagnostics,
            );
            let tasks = worker_states
                .get(worker_id)
                .and_then(|s| s.get("completed_tasks"))
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let mut tasks = tasks;
            tasks.push(json!(task.task_id));
            worker_states.insert(
                worker_id.clone(),
                json!({"status":"ready","completed_tasks":tasks}),
            );
            trace.push(json!({"event":"task_complete","logical_step":logical_step,"task_id":task.task_id,"worker_id":worker_id,"attempt":attempt}));
            if let Some(runtime) = result.get("runtime") {
                runtime_outputs.push(runtime.clone());
                for event in runtime
                    .pointer("/metadata/tensor_trace")
                    .and_then(Value::as_array)
                    .into_iter()
                    .flatten()
                {
                    trace.push(json!({"event":"tensor_execute","logical_step":logical_step,"task_id":task.task_id,"worker_id":worker_id,"runtime_event":event}));
                }
            }
        }
        if config.execution.sync_policy == "barrier" {
            let unique: BTreeSet<_> = assigned.iter().collect();
            for worker in &unique {
                log.send(worker, coordinator, "barrier_wait", logical_step, json!({"completed_task_ids":tasks.iter().map(|t| &t.task_id).collect::<Vec<_>>()}))?;
            }
            for worker in &unique {
                log.send(
                    coordinator,
                    worker,
                    "barrier_release",
                    logical_step,
                    json!({"next_logical_step":logical_step+1}),
                )?;
            }
            trace.push(json!({"event":"barrier_release","logical_step":logical_step,"task_ids":tasks.iter().map(|t| &t.task_id).collect::<Vec<_>>()}));
        }
        state_version += 1;
        let pending = task_states
            .iter()
            .filter(|(_, state)| **state != "completed")
            .map(|(id, _)| id.clone())
            .collect();
        let snapshot = StateSnapshot::new(
            &run_id,
            logical_step,
            state_version,
            serde_json::to_value(&worker_states).map_err(|e| e.to_string())?,
            json!({"semantic_final_state":semantic_projection(bundle).get("final_state")}),
            completed.clone(),
            pending,
        )
        .map_err(|e| e.to_string())?;
        if serde_json::to_vec(&snapshot)
            .map_or(true, |bytes| bytes.len() > config.limits.max_state_bytes)
        {
            diagnostics.push(Diagnostic::error(
                "CRR-STA-005",
                "State snapshot exceeds max_state_bytes",
                logical_step.to_string(),
            ));
            break;
        }
        snapshots.push(snapshot);
    }
    for worker in &workers {
        log.send(
            coordinator,
            worker,
            "shutdown",
            state_version + 1,
            json!({}),
        )?;
    }
    let nodes: HashSet<_> = std::iter::once(coordinator.clone())
        .chain(workers.iter().cloned())
        .collect();
    diagnostics.extend(validate_stream(
        &log.items,
        &nodes,
        config.limits.max_message_bytes,
    ));
    if completed.len() != plan.tasks.len() {
        diagnostics.push(Diagnostic::error(
            "CRR-RUN-008",
            "Incomplete tasks remain",
            "tasks",
        ));
    }
    sort(&mut diagnostics);
    let semantics = semantic_projection(bundle);
    let evaluation = evaluate(
        &plan.tasks,
        &completed,
        &log.items,
        &trace,
        retries,
        workers.len(),
        &semantics,
        &semantics,
        fallback,
    );
    let status = if evaluation.passed && !diagnostics.iter().any(|d| d.severity == "error") {
        "completed"
    } else {
        "failed"
    };
    let runtime_results: Vec<Value> = trace
        .iter()
        .filter(|event| event.get("event").and_then(Value::as_str) == Some("tensor_execute"))
        .cloned()
        .collect();
    let calculation_results: Vec<Value> = runtime_outputs
        .iter()
        .filter_map(|output| output.get("calculation_results").cloned())
        .collect();
    let tensor_metadata: Vec<Value> = runtime_outputs
        .iter()
        .flat_map(|output| {
            output
                .pointer("/metadata/tensor_metadata")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .cloned()
        })
        .collect();
    let summary = json!({"schema_version":"reasonscript-cluster-run-summary/0.1","run_id":run_id,"status":status,"mode":if fallback{"single_node"}else{&config.mode},"fallback_used":fallback,"task_counts":{"total":plan.tasks.len(),"completed":completed.len(),"failed":plan.tasks.len()-completed.len()},"semantic_result":semantics,"runtime":{"workloads":plan.tasks.iter().filter(|task| task.runtime_workload.is_some()).count(),"calculation_results":calculation_results,"tensor_metadata":tensor_metadata,"tensor_trace_events":runtime_results.len()},"evaluation_status":evaluation.status,"diagnostic_count":diagnostics.len()});
    finish(
        config,
        &plan,
        &run_id,
        worker_states,
        log.items,
        trace,
        snapshots,
        diagnostics,
        serde_json::to_value(evaluation).map_err(|e| e.to_string())?,
        summary,
        options,
    )
}

fn execute_local_processes(
    tasks: &[ReasonTask],
    state_version: usize,
    timeout_ms: u64,
    runtime: &RuntimeContext,
) -> Result<Vec<Value>, String> {
    let executable = std::env::current_exe().map_err(|e| format!("CRR-RUN-004: {e}"))?;
    let mut children = Vec::new();
    for task in tasks {
        let mut child = Command::new(&executable)
            .arg("internal-worker")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("CRR-RUN-004: {e}"))?;
        let request = json!({"task":task,"state_version":state_version,"runtime":runtime});
        let mut worker_stdin = child
            .stdin
            .take()
            .ok_or("CRR-RUN-001: worker stdin unavailable")?;
        worker_stdin
            .write_all(
                serde_json::to_string(&request)
                    .map_err(|e| e.to_string())?
                    .as_bytes(),
            )
            .map_err(|e| format!("CRR-RUN-004: {e}"))?;
        drop(worker_stdin);
        children.push((child, Instant::now()));
    }
    let mut results = Vec::new();
    for (mut child, started) in children {
        loop {
            if child
                .try_wait()
                .map_err(|e| format!("CRR-RUN-004: {e}"))?
                .is_some()
            {
                break;
            }
            if started.elapsed() >= Duration::from_millis(timeout_ms) {
                let _ = child.kill();
                let _ = child.wait();
                return Err("CRR-RUN-003: Task timeout".into());
            }
            thread::sleep(Duration::from_millis(1));
        }
        let output = child
            .wait_with_output()
            .map_err(|e| format!("CRR-RUN-004: {e}"))?;
        if !output.status.success() {
            return Err(format!(
                "CRR-RUN-004: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        results
            .push(serde_json::from_slice(&output.stdout).map_err(|e| format!("CRR-RUN-004: {e}"))?);
    }
    Ok(results)
}

fn transition(
    states: &mut HashMap<String, &str>,
    task: &str,
    target: &'static str,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let current = states.get(task).copied().unwrap_or("unknown");
    let valid = matches!(
        (current, target),
        ("pending", "ready")
            | ("ready", "assigned")
            | ("assigned", "running")
            | ("running", "completed")
            | ("running", "waiting")
            | ("running", "failed")
            | ("waiting", "running")
            | ("failed", "assigned")
            | ("failed", "cancelled")
            | ("pending", "skipped")
            | ("ready", "cancelled")
    );
    if valid {
        states.insert(task.into(), target);
    } else {
        diagnostics.push(Diagnostic::error(
            "CRR-RUN-006",
            format!("Invalid task transition {current} -> {target}"),
            task,
        ));
    }
}

fn finish(
    config: &ClusterConfig,
    plan: &ClusterPlan,
    run_id: &str,
    worker_states: BTreeMap<String, Value>,
    messages: Vec<ClusterMessage>,
    trace: Vec<Value>,
    snapshots: Vec<StateSnapshot>,
    diagnostics: Vec<Diagnostic>,
    evaluation: Value,
    summary: Value,
    options: &RunOptions,
) -> Result<ClusterRun, String> {
    let mut nodes = vec![
        json!({"node_id":config.coordinator.node_id,"role":"coordinator","status":summary["status"]}),
    ];
    for (id, state) in worker_states {
        nodes.push(json!({"node_id":id,"role":"worker","status":state["status"],"completed_tasks":state["completed_tasks"]}));
    }
    let mut documents = BTreeMap::from([
        (
            "cluster_manifest.json".into(),
            json!({"schema_version":"reasonscript-cluster-manifest/0.1","run_id":run_id,"cluster_id":config.cluster_id,"mode":summary["mode"],"status":summary["status"],"artifacts":[]}),
        ),
        (
            "cluster_plan.json".into(),
            serde_json::to_value(plan).map_err(|e| e.to_string())?,
        ),
        (
            "cluster_nodes.json".into(),
            json!({"schema_version":"reasonscript-cluster-nodes/0.1","run_id":run_id,"nodes":nodes}),
        ),
        (
            "cluster_messages.jsonl".into(),
            serde_json::to_value(messages).map_err(|e| e.to_string())?,
        ),
        (
            "cluster_trace.json".into(),
            json!({"schema_version":"reasonscript-cluster-trace/0.1","run_id":run_id,"events":trace}),
        ),
        (
            "cluster_state.json".into(),
            json!({"schema_version":"reasonscript-cluster-state-history/0.1","run_id":run_id,"final_snapshot":snapshots.last(),"snapshots":snapshots}),
        ),
        (
            "cluster_diagnostics.json".into(),
            json!({"schema_version":"reasonscript-cluster-diagnostics/0.1","run_id":run_id,"diagnostics":diagnostics}),
        ),
        ("cluster_evaluation_report.json".into(), evaluation),
        ("cluster_run_summary.json".into(), summary.clone()),
    ]);
    if let Some(directory) = &options.artifacts_dir {
        let manifest = write_artifacts(directory, &documents)?;
        documents.insert("cluster_manifest.json".into(), manifest);
    }
    Ok(ClusterRun { summary, documents })
}

fn finish_failed(
    bundle: &Value,
    config: &ClusterConfig,
    plan: &ClusterPlan,
    run_id: &str,
    mut diagnostics: Vec<Diagnostic>,
    options: &RunOptions,
) -> Result<ClusterRun, String> {
    sort(&mut diagnostics);
    let count = diagnostics.len();
    let summary = json!({"schema_version":"reasonscript-cluster-run-summary/0.1","run_id":run_id,"status":"failed","mode":config.mode,"fallback_used":false,"task_counts":{"total":plan.tasks.len(),"completed":0,"failed":plan.tasks.len()},"semantic_result":semantic_projection(bundle),"evaluation_status":"failed","diagnostic_count":count});
    finish(
        config,
        plan,
        run_id,
        BTreeMap::new(),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        diagnostics,
        json!({"schema_version":"reasonscript-cluster-evaluation-report/0.1","status":"failed","passed":false,"correctness":{},"determinism":{},"equivalence":{},"efficiency":{},"fallback_used":false}),
        summary,
        options,
    )
}
