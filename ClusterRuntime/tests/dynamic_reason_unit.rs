use std::fs;

use reasonscript_cluster_runtime::{
    config::ClusterConfig,
    dynamic::{
        artifacts::{validate_dynamic_directory, DYNAMIC_ARTIFACT_FILES},
        config::DynamicConfig,
        lifecycle::allowed,
        runtime::{run_dynamic, DynamicOptions},
        test_model,
    },
};

#[test]
fn all_dynamic_and_molecular_test_models_pass() {
    for scenario in test_model::SCENARIOS {
        let result = test_model::run(scenario, 4).unwrap();
        assert_eq!(result["passed"], true, "{scenario}: {result}");
    }
}

#[test]
fn lifecycle_rejects_terminal_reactivation() {
    assert!(!allowed(Some("retired"), "ready"));
    assert!(!allowed(Some("replaced"), "ready"));
    assert!(!allowed(Some("cancelled"), "ready"));
    assert!(allowed(Some("suspended"), "ready"));
}

#[test]
fn writes_and_offline_validates_all_dynamic_artifacts() {
    let root = std::env::temp_dir().join(format!("reason-dynamic-test-{}", std::process::id()));
    if root.exists() {
        fs::remove_dir_all(&root).unwrap();
    }
    let bundle = reasonscript_cluster_runtime::test_model::bundle("dependency-chain").unwrap();
    let result = run_dynamic(
        &bundle,
        &ClusterConfig::local(2, "simulation"),
        &DynamicConfig::default(),
        &DynamicOptions {
            artifacts_dir: Some(root.clone()),
            scenario: Some("dynamic-generation".into()),
        },
    )
    .unwrap();
    assert_eq!(result.summary["status"], "converged");
    for name in DYNAMIC_ARTIFACT_FILES {
        assert!(root.join(name).is_file(), "{name}");
    }
    assert_eq!(validate_dynamic_directory(&root)["valid"], true);
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn budget_termination_is_not_reported_as_convergence() {
    let result = test_model::run("budget-termination", 4).unwrap();
    assert_eq!(result["run"]["status"], "budget_terminated");
    assert_ne!(result["run"]["status"], "converged");
}
