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
            task_id: "vision-b".into(),
            runtime_type: "VISION".into(),
            input_state: second,
            goal: "EXTRACT_OBJECTS".into(),
            resource_hint: json!({"estimated_operations":3}),
            dependencies: vec![],
            provenance: vec!["fixture".into()],
        },
        RuntimeTask {
            task_id: "geometry".into(),
            runtime_type: "GEOMETRY".into(),
            input_state: Value::Null,
            goal: "CALCULATE_SPATIAL_RELATIONS".into(),
            resource_hint: json!({"estimated_operations":4}),
            dependencies: vec!["vision-a".into(), "vision-b".into()],
            provenance: vec![],
        },
        RuntimeTask {
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
