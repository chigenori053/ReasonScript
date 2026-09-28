use reasonscript_cluster_runtime::visual::{run_visual, RuntimeTask, VisualLimits};
use serde_json::{json, Value};
fn source() -> Value {
    serde_json::from_str(include_str!(
        "../../tests/fixtures/vision_runtime/solar_observation.json"
    ))
    .unwrap()
}
fn tasks() -> Vec<RuntimeTask> {
    let first = source();
    let mut second = first.clone();
    second["observation_id"] = json!("obs:second");
    second["detections"][0]["detection_id"] = json!("det:second:one");
    second["detections"][1]["detection_id"] = json!("det:second:two");
    vec![
        RuntimeTask {
            schema_version: "reasonscript-runtime-task/1.0".into(),
            task_id: "vision-b".into(),
            runtime_type: "VISION".into(),
            input_state: second,
            goal: "EXTRACT_OBJECTS".into(),
            resource_hint: json!({"estimated_operations":3}),
            dependencies: vec![],
            provenance: vec!["fixture".into()],
        },
        RuntimeTask {
            schema_version: "reasonscript-runtime-task/1.0".into(),
            task_id: "geometry".into(),
            runtime_type: "GEOMETRY".into(),
            input_state: Value::Null,
            goal: "CALCULATE_SPATIAL_RELATIONS".into(),
            resource_hint: json!({"estimated_operations":4}),
            dependencies: vec!["vision-a".into(), "vision-b".into()],
            provenance: vec![],
        },
        RuntimeTask {
            schema_version: "reasonscript-runtime-task/1.0".into(),
            task_id: "vision-a".into(),
            runtime_type: "VISION".into(),
            input_state: first,
            goal: "EXTRACT_OBJECTS".into(),
            resource_hint: json!({"estimated_operations":3}),
            dependencies: vec![],
            provenance: vec!["fixture".into()],
        },
    ]
}
#[test]
fn clustered_and_local_are_equivalent_three_times() {
    let tasks = tasks();
    let clustered = VisualLimits::default();
    let local = VisualLimits {
        max_workers: 1,
        ..clustered.clone()
    };
    let expected = run_visual(&tasks, &local).unwrap();
    assert_eq!(expected.decision, "local");
    for _ in 0..3 {
        let actual = run_visual(&tasks, &clustered).unwrap();
        assert_eq!(actual.decision, "cluster");
        assert_eq!(actual.semantic_state, expected.semantic_state);
        assert_eq!(actual.geometry_state, expected.geometry_state);
        assert!(actual
            .task_outputs
            .iter()
            .all(|o| !o.trace.provenance.is_empty()));
        let mut reordered = tasks.clone();
        reordered.reverse();
        assert_eq!(
            run_visual(&reordered, &clustered).unwrap().semantic_state,
            actual.semantic_state
        )
    }
}
#[test]
fn resource_limits_and_dependencies() {
    let tasks = tasks();
    assert!(run_visual(
        &tasks,
        &VisualLimits {
            max_operations: 2,
            ..VisualLimits::default()
        }
    )
    .unwrap_err()
    .starts_with("RESOURCE_LIMIT"));
    assert!(run_visual(
        &tasks,
        &VisualLimits {
            max_state_size: 1,
            ..VisualLimits::default()
        }
    )
    .unwrap_err()
    .starts_with("RESOURCE_LIMIT"));
    let mut broken = tasks.clone();
    broken[1].dependencies.push("missing".into());
    assert!(run_visual(&broken, &VisualLimits::default())
        .unwrap_err()
        .contains("dependency"));
    let mut cyclic = tasks.clone();
    cyclic[0].dependencies.push("geometry".into());
    assert!(run_visual(&cyclic, &VisualLimits::default())
        .unwrap_err()
        .contains("cycle"))
}

#[test]
fn exact_budget_and_dispatch_boundaries() {
    let tasks = tasks();
    let expected = run_visual(&tasks, &VisualLimits::default()).unwrap();
    assert!(expected.operations > 0);
    assert_eq!(
        run_visual(
            &tasks,
            &VisualLimits {
                max_operations: expected.operations,
                ..VisualLimits::default()
            }
        )
        .unwrap()
        .operations,
        expected.operations
    );
    assert!(run_visual(
        &tasks,
        &VisualLimits {
            max_operations: expected.operations - 1,
            ..VisualLimits::default()
        }
    )
    .unwrap_err()
    .starts_with("RESOURCE_LIMIT"));
    assert!(expected.task_outputs.iter().all(|o| o
        .trace
        .operations
        .iter()
        .any(|event| event["worker_lifecycle"].is_array())));
    let empty = run_visual(&[], &VisualLimits::default()).unwrap();
    assert_eq!(empty.operations, 0);
    assert!(empty.semantic_state.is_null());
    let mut invalid = tasks.clone();
    invalid[0].runtime_type = "UNKNOWN".into();
    assert!(run_visual(&invalid, &VisualLimits::default()).is_err());
    assert!(run_visual(
        &tasks,
        &VisualLimits {
            max_workers: 0,
            ..VisualLimits::default()
        }
    )
    .unwrap_err()
    .starts_with("RESOURCE_LIMIT"));
}

#[test]
fn registry_contract_and_unknown_runtime() {
    use reasonscript_cluster_runtime::visual::{
        default_registry, RuntimeRegistry, VisionRuntimeAdapter,
    };
    let mut registry = RuntimeRegistry::default();
    registry.register(Box::new(VisionRuntimeAdapter)).unwrap();
    assert!(registry
        .register(Box::new(VisionRuntimeAdapter))
        .unwrap_err()
        .contains("duplicate"));
    assert!(registry
        .get("MATH")
        .err()
        .unwrap()
        .starts_with("UNSUPPORTED_RUNTIME"));
    assert_eq!(
        default_registry().get("GEOMETRY").unwrap().runtime_type(),
        "GEOMETRY"
    );
    let mut task = tasks().remove(0);
    task.runtime_type = "MATH".into();
    assert!(run_visual(&[task], &VisualLimits::default())
        .unwrap_err()
        .starts_with("UNSUPPORTED_RUNTIME"));
}

#[test]
fn canonical_artifacts_match_across_workers_order_and_repetitions() {
    for seed in 0..3 {
        let mut original = tasks();
        for task in &mut original {
            task.task_id = format!("case-{seed}:{}", task.task_id);
            task.dependencies = task
                .dependencies
                .iter()
                .map(|id| format!("case-{seed}:{id}"))
                .collect();
            if task.runtime_type == "VISION" {
                task.input_state["observation_id"] = json!(format!("case-{seed}:{}", task.task_id));
                for (index, detection) in task.input_state["detections"]
                    .as_array_mut()
                    .unwrap()
                    .iter_mut()
                    .enumerate()
                {
                    detection["detection_id"] =
                        json!(format!("case-{seed}:{}:{index}", task.task_id));
                }
            }
        }
        let mut expected = None;
        for _ in 0..3 {
            for workers in [1, 2, 4] {
                for reversed in [false, true] {
                    let mut tasks = original.clone();
                    if reversed {
                        tasks.reverse();
                    }
                    let run = run_visual(
                        &tasks,
                        &VisualLimits {
                            max_workers: workers,
                            ..VisualLimits::default()
                        },
                    )
                    .unwrap();
                    assert_eq!(run.decision, if workers == 1 { "local" } else { "cluster" });
                    let canonical = json!({"geometry_state":run.geometry_state,"semantic_state":run.semantic_state,
                    "outputs":run.task_outputs.iter().map(|output| json!({"task_id":output.task_id,
                        "output_state":output.output_state,"semantic_state":output.semantic_state,
                        "provenance":output.provenance,"trace":output.trace,"status":output.status})).collect::<Vec<_>>()});
                    if let Some(ref value) = expected {
                        assert_eq!(&canonical, value);
                    } else {
                        expected = Some(canonical);
                    }
                }
            }
        }
    }
}

#[test]
fn output_envelope_and_scheduler_boundaries() {
    use reasonscript_cluster_runtime::visual::{
        GeometryRuntimeAdapter, RuntimeAdapter, OUTPUT_SCHEMA, RUNTIME_SCHEMA,
    };
    let tasks = tasks();
    let local = run_visual(
        &tasks,
        &VisualLimits {
            local_threshold: usize::MAX,
            ..VisualLimits::default()
        },
    )
    .unwrap();
    assert_eq!(local.decision, "local");
    assert_eq!(local.scheduling.threshold, usize::MAX);
    let cluster = run_visual(&tasks, &VisualLimits::default()).unwrap();
    assert_eq!(cluster.decision, "cluster");
    assert!(cluster.scheduling.workload.parallel_units > 1);
    for output in &cluster.task_outputs {
        assert_eq!(output.schema_version, OUTPUT_SCHEMA);
        assert_eq!(output.status, "COMPLETED");
        assert_eq!(
            output.trace.worker_id,
            format!("worker:{}:{}", output.runtime_type, output.task_id)
        );
        assert_eq!(
            output.trace.operations[0]["worker_lifecycle"],
            json!([
                "CREATE",
                "DISPATCH",
                "EXECUTE",
                "COLLECT",
                "MERGE",
                "TERMINATE"
            ])
        );
        assert!(!output.provenance.is_empty());
    }
    let mut bad = tasks.clone();
    bad[0].schema_version = "future".into();
    assert!(run_visual(&bad, &VisualLimits::default())
        .unwrap_err()
        .contains("schema_version"));
    let mut bad = tasks.clone();
    bad[0].dependencies.push("geometry".into());
    assert!(run_visual(&bad, &VisualLimits::default())
        .unwrap_err()
        .contains("cycle"));
    assert_eq!(tasks[0].schema_version, RUNTIME_SCHEMA);
    let adapter = GeometryRuntimeAdapter;
    let units = adapter.decompose(
        &tasks[1],
        &cluster
            .task_outputs
            .iter()
            .filter(|o| o.runtime_type == "VISION")
            .cloned()
            .collect::<Vec<_>>(),
    );
    assert!(units.len() > 1);
    assert!(units.windows(2).all(|pair| pair[0] < pair[1]));
}

#[test]
fn unknown_conflict_and_resource_boundaries() {
    let base = run_visual(&tasks(), &VisualLimits::default())
        .unwrap()
        .geometry_state
        .unwrap();
    let mut unknown = base.clone();
    unknown
        .unknowns
        .push(json!({"subject":"generated","status":"UNKNOWN","provenance":["missing-evidence"]}));
    let geometry_task = |id: &str, state: Value| RuntimeTask {
        schema_version: "reasonscript-runtime-task/1.0".into(),
        task_id: id.into(),
        runtime_type: "GEOMETRY".into(),
        input_state: state,
        goal: "CALCULATE_SPATIAL_RELATIONS".into(),
        resource_hint: Value::Null,
        dependencies: vec![],
        provenance: vec![id.into()],
    };
    let result = run_visual(
        &[geometry_task("unknown", json!(unknown))],
        &VisualLimits::default(),
    )
    .unwrap();
    assert_eq!(result.status, "UNKNOWN");
    assert!(!result.geometry_state.unwrap().unknowns.is_empty());
    let mut changed = base.clone();
    if changed.primitives[0].geometry_type == "BoundingBox" {
        changed.primitives[0].parameters["xywh"][0] = json!(999.0);
    } else {
        changed.primitives[0].parameters["xy"][0] = json!(999.0);
    }
    changed.primitives[0]
        .provenance
        .push("conflict-source".into());
    let result = run_visual(
        &[
            geometry_task("a", json!(base)),
            geometry_task("b", json!(changed)),
        ],
        &VisualLimits::default(),
    )
    .unwrap();
    assert_eq!(result.status, "CONFLICT");
    assert!(result
        .geometry_state
        .unwrap()
        .conflicts
        .iter()
        .any(|v| v["status"] == "CONFLICT"));
    for limits in [
        VisualLimits {
            timeout_ms: 0,
            ..VisualLimits::default()
        },
        VisualLimits {
            max_memory: 1,
            ..VisualLimits::default()
        },
        VisualLimits {
            max_state_size: 1,
            ..VisualLimits::default()
        },
    ] {
        assert!(run_visual(&tasks(), &limits)
            .unwrap_err()
            .starts_with("RESOURCE_LIMIT"));
    }
}

#[test]
fn elapsed_timeout_and_output_memory_are_explicit_limits() {
    use reasonscript_cluster_runtime::visual::{
        run_runtime, RuntimeAdapter, RuntimeRegistry, RuntimeWorkload, TaskOutput,
        VisionRuntimeAdapter,
    };
    struct SlowVision;
    impl RuntimeAdapter for SlowVision {
        fn runtime_type(&self) -> &'static str {
            "VISION"
        }
        fn validate_task(&self, task: &RuntimeTask) -> Result<(), String> {
            VisionRuntimeAdapter.validate_task(task)
        }
        fn estimate_workload(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> RuntimeWorkload {
            VisionRuntimeAdapter.estimate_workload(task, deps)
        }
        fn decompose(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> Vec<String> {
            VisionRuntimeAdapter.decompose(task, deps)
        }
        fn execute(&self, task: &RuntimeTask, deps: &[TaskOutput]) -> Result<TaskOutput, String> {
            std::thread::sleep(std::time::Duration::from_millis(10));
            VisionRuntimeAdapter.execute(task, deps)
        }
        fn canonicalize_output(&self, output: &mut TaskOutput) -> Result<(), String> {
            VisionRuntimeAdapter.canonicalize_output(output)
        }
    }
    let task = tasks().remove(0);
    let mut registry = RuntimeRegistry::default();
    registry.register(Box::new(SlowVision)).unwrap();
    assert!(run_runtime(
        &[task.clone()],
        &VisualLimits {
            timeout_ms: 1,
            ..VisualLimits::default()
        },
        &registry
    )
    .unwrap_err()
    .contains("TIMEOUT"));
    let input_size = serde_json::to_vec(&vec![task.clone()]).unwrap().len();
    let unrestricted = run_visual(&[task.clone()], &VisualLimits::default()).unwrap();
    let output_size = serde_json::to_vec(&unrestricted).unwrap().len();
    assert!(output_size > input_size);
    assert!(run_visual(
        &[task],
        &VisualLimits {
            max_memory: input_size + 1,
            ..VisualLimits::default()
        }
    )
    .unwrap_err()
    .contains("memory budget"));
}
