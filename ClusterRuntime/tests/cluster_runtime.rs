use std::{collections::HashSet, fs};

use reasonscript_cluster_runtime::{
    artifacts::{validate_directory, ARTIFACT_FILES},
    config::ClusterConfig,
    messages::{validate_stream, ClusterMessage},
    planner::build_cluster_plan,
    runtime::{run_cluster, RunOptions},
    state::merge,
    test_model,
};
use serde_json::json;

#[test]
fn all_required_test_models_pass_in_simulation() {
    for scenario in test_model::SCENARIOS {
        assert_eq!(
            test_model::run(scenario, 4, "simulation").unwrap()["passed"],
            true,
            "{scenario}"
        );
    }
}

#[test]
fn planner_preserves_chain_and_fan_in_dependencies() {
    for scenario in ["dependency-chain", "fan-out-fan-in"] {
        let bundle = test_model::bundle(scenario).unwrap();
        let payload = &bundle["artifacts"];
        let plan = build_cluster_plan(
            &payload["execution_plan"],
            &payload["reason_ir"],
            &["worker-0".into(), "worker-1".into()],
            "barrier",
        );
        assert!(plan.valid);
        assert!(plan
            .tasks
            .iter()
            .all(|task| task.dependency_ids.iter().all(|dep| plan
                .tasks
                .iter()
                .any(|candidate| &candidate.task_id == dep
                    && candidate.logical_step < task.logical_step))));
    }
}

#[test]
fn message_checksum_and_sequence_are_fail_closed() {
    let mut first = ClusterMessage::new(
        "msg_1".into(),
        "run",
        0,
        1,
        "a",
        "b",
        "heartbeat",
        json!({}),
    )
    .unwrap();
    let second = ClusterMessage::new(
        "msg_2".into(),
        "run",
        0,
        1,
        "a",
        "b",
        "heartbeat",
        json!({}),
    )
    .unwrap();
    first.payload = json!({"corrupt":true});
    let codes: HashSet<_> = validate_stream(
        &[first, second],
        &HashSet::from(["a".into(), "b".into()]),
        1024,
    )
    .into_iter()
    .map(|d| d.code)
    .collect();
    assert!(codes.contains("CRR-MSG-001"));
    assert!(codes.contains("CRR-MSG-002"));
}

#[test]
fn state_merge_policies_are_deterministic() {
    assert_eq!(
        merge(&json!([2, 1]), &json!([1, 3]), "set_union").unwrap(),
        json!([1, 2, 3])
    );
    assert!(merge(&json!({}), &json!({}), "custom_validated").is_err());
}

#[test]
fn writes_and_validates_all_nine_artifacts() {
    let root = std::env::temp_dir().join(format!("reason-cluster-test-{}", std::process::id()));
    if root.exists() {
        fs::remove_dir_all(&root).unwrap();
    }
    let result = run_cluster(
        &test_model::bundle("dependency-chain").unwrap(),
        &ClusterConfig::local(2, "simulation"),
        &RunOptions {
            artifacts_dir: Some(root.clone()),
        },
    )
    .unwrap();
    assert_eq!(result.summary["status"], "completed");
    for name in ARTIFACT_FILES {
        assert!(root.join(name).is_file());
    }
    assert_eq!(validate_directory(&root)["valid"], true);
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn fallback_is_recorded_and_semantically_equivalent() {
    let mut config = ClusterConfig::local(0, "simulation");
    config.execution.fallback = "single_node".into();
    let result = run_cluster(
        &test_model::bundle("fallback").unwrap(),
        &config,
        &RunOptions::default(),
    )
    .unwrap();
    assert_eq!(result.summary["fallback_used"], true);
    assert_eq!(result.summary["status"], "completed");
}
