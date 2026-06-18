/// TestPlayground v0.1 — Integration tests
///
/// Each test invokes the binary through `cargo run` to validate that the
/// full pipeline (parse → AST → Semantic AST → Reason IR → Validation)
/// works end-to-end for the example suite.
use std::path::Path;
use std::process::Command;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn repo_root() -> &'static Path {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap()
}

fn examples_dir() -> std::path::PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("examples")
}

/// Run the testplayground binary against a source file and return stdout.
fn run_cmd(subcommand: &str, source: &str) -> (bool, String, String) {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let script = Path::new(manifest_dir).join("scripts").join("pipeline.py");

    let output = Command::new("python3")
        .arg(&script)
        .arg(subcommand)
        .arg(source)
        .arg("--format")
        .arg("pretty")
        .current_dir(repo_root())
        .output()
        .expect("failed to run pipeline script");

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    (output.status.success(), stdout, stderr)
}

fn run_json(subcommand: &str, source: &str) -> (bool, String) {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let script = Path::new(manifest_dir).join("scripts").join("pipeline.py");

    let output = Command::new("python3")
        .arg(&script)
        .arg(subcommand)
        .arg(source)
        .arg("--format")
        .arg("json")
        .current_dir(repo_root())
        .output()
        .expect("failed to run pipeline script");

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    (output.status.success(), stdout)
}

// ---------------------------------------------------------------------------
// TP-001: Parser success
// ---------------------------------------------------------------------------

#[test]
fn tp001_parse_minimal_goal() {
    let src = examples_dir().join("graph/ex_001_minimal_goal.rsn");
    let (ok, stdout, _) = run_cmd("parse", src.to_str().unwrap());
    assert!(ok, "parse should succeed for minimal goal");
    assert!(stdout.contains("Parse Success"));
}

#[test]
fn tp001_parse_state_transition() {
    let src = examples_dir().join("graph/ex_002_state_transition.rsn");
    let (ok, _, _) = run_cmd("parse", src.to_str().unwrap());
    assert!(ok);
}

#[test]
fn tp001_parse_taxonomy() {
    let src = examples_dir().join("graph/ex_003_taxonomy.rsn");
    let (ok, _, _) = run_cmd("parse", src.to_str().unwrap());
    assert!(ok);
}

#[test]
fn tp001_parse_navigation() {
    let src = examples_dir().join("planning/ex_004_navigation.rsn");
    let (ok, _, _) = run_cmd("parse", src.to_str().unwrap());
    assert!(ok);
}

#[test]
fn tp001_parse_multi_step() {
    let src = examples_dir().join("planning/ex_005_multi_step.rsn");
    let (ok, _, _) = run_cmd("parse", src.to_str().unwrap());
    assert!(ok);
}

#[test]
fn tp001_parse_concept_graph() {
    let src = examples_dir().join("graph/ex_008_concept_graph.rsn");
    let (ok, _, _) = run_cmd("parse", src.to_str().unwrap());
    assert!(ok);
}

#[test]
fn tp001_parse_planning_module() {
    let src = examples_dir().join("planning/ex_009_planning_module.rsn");
    let (ok, _, _) = run_cmd("parse", src.to_str().unwrap());
    assert!(ok);
}

// ---------------------------------------------------------------------------
// TP-002: AST display success
// ---------------------------------------------------------------------------

#[test]
fn tp002_ast_json_minimal_goal() {
    let src = examples_dir().join("graph/ex_001_minimal_goal.rsn");
    let (ok, stdout) = run_json("ast", src.to_str().unwrap());
    assert!(ok, "ast command should succeed");
    let parsed: serde_json::Value = serde_json::from_str(&stdout)
        .expect("ast output should be valid JSON");
    // Phase 2 AST: ModuleNode with declarations
    let has_goal = parsed
        .get("declarations")
        .and_then(|d| d.as_array())
        .map(|arr| arr.iter().any(|n| n.get("node_type").and_then(|t| t.as_str()) == Some("GoalNode")))
        .unwrap_or(false);
    assert!(has_goal, "AST should contain a GoalNode");
}

#[test]
fn tp002_ast_json_taxonomy() {
    let src = examples_dir().join("graph/ex_003_taxonomy.rsn");
    let (ok, stdout) = run_json("ast", src.to_str().unwrap());
    assert!(ok);
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    let decls = parsed["declarations"].as_array().unwrap();
    let transition_count = decls.iter()
        .filter(|n| n.get("node_type").and_then(|t| t.as_str()) == Some("TransitionNode"))
        .count();
    assert_eq!(transition_count, 2, "taxonomy should have 2 transitions");
}

// ---------------------------------------------------------------------------
// TP-003: Semantic AST display success
// ---------------------------------------------------------------------------

#[test]
fn tp003_semantic_ast_phase2() {
    let src = examples_dir().join("graph/ex_002_state_transition.rsn");
    let (ok, stdout) = run_json("semantic", src.to_str().unwrap());
    assert!(ok, "semantic command should succeed");
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert_eq!(
        parsed["version"].as_str().unwrap_or(""),
        "reasonscript-ast/0.1",
        "semantic AST version should be reasonscript-ast/0.1"
    );
}

#[test]
fn tp003_semantic_ast_surface() {
    let src = examples_dir().join("planning/ex_009_planning_module.rsn");
    let (ok, _, stderr) = run_cmd("semantic", src.to_str().unwrap());
    assert!(ok, "semantic command should succeed for surface file: {}", stderr);
}

// ---------------------------------------------------------------------------
// TP-004: Reason IR display success
// ---------------------------------------------------------------------------

#[test]
fn tp004_ir_basic_inference() {
    let src = examples_dir().join("graph/ex_002_state_transition.rsn");
    let (ok, stdout) = run_json("ir", src.to_str().unwrap());
    assert!(ok, "ir command should succeed");
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert_eq!(
        parsed["schema_version"].as_str().unwrap_or(""),
        "reason-ir/0.1",
        "IR should have schema_version reason-ir/0.1"
    );
    assert!(
        parsed["goal"].is_object(),
        "IR should contain a goal field"
    );
}

#[test]
fn tp004_ir_taxonomy() {
    let src = examples_dir().join("graph/ex_003_taxonomy.rsn");
    let (ok, stdout) = run_json("ir", src.to_str().unwrap());
    assert!(ok);
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    let transitions = parsed["transitions"].as_array().unwrap();
    assert_eq!(transitions.len(), 2);
}

#[test]
fn tp004_ir_with_constraint() {
    let src = examples_dir().join("planning/ex_004_navigation.rsn");
    let (ok, stdout) = run_json("ir", src.to_str().unwrap());
    assert!(ok);
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    let constraints = parsed.get("constraints")
        .and_then(|c| c.as_array())
        .map(|a| a.len())
        .unwrap_or(0);
    assert_eq!(constraints, 1, "IR should include 1 constraint");
}

// ---------------------------------------------------------------------------
// TP-005: Validation success
// ---------------------------------------------------------------------------

#[test]
fn tp005_validate_minimal_goal() {
    let src = examples_dir().join("graph/ex_001_minimal_goal.rsn");
    let (ok, stdout, _) = run_cmd("validate", src.to_str().unwrap());
    assert!(ok, "validation should pass for minimal goal");
    assert!(
        stdout.contains("Validation PASS"),
        "output should contain 'Validation PASS'"
    );
}

#[test]
fn tp005_validate_full_pipeline() {
    for path in &[
        "graph/ex_001_minimal_goal.rsn",
        "graph/ex_002_state_transition.rsn",
        "graph/ex_003_taxonomy.rsn",
        "planning/ex_004_navigation.rsn",
        "planning/ex_005_multi_step.rsn",
        "constraint/ex_006_door.rsn",
        "constraint/ex_007_multi_constraint.rsn",
    ] {
        let src = examples_dir().join(path);
        let (ok, stdout, stderr) = run_cmd("validate", src.to_str().unwrap());
        assert!(
            ok,
            "validation should pass for {}: stderr={}",
            path, stderr
        );
        assert!(
            stdout.contains("Validation PASS"),
            "output should contain 'Validation PASS' for {}",
            path
        );
    }
}

// ---------------------------------------------------------------------------
// TP-007: Runtime integration
// ---------------------------------------------------------------------------

#[test]
fn tp007_run_single_transition() {
    let src = examples_dir().join("graph/ex_002_state_transition.rsn");
    let (ok, stdout) = run_json("run", src.to_str().unwrap());
    assert!(ok, "run command should execute the runtime pipeline");
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert_eq!(parsed["status"].as_str().unwrap_or(""), "success");
    assert_eq!(parsed["goal_reached"].as_bool(), Some(true));
    assert_eq!(parsed["final_state"].as_str().unwrap_or(""), "Kitchen");
    assert_eq!(
        parsed["trace"].as_array().unwrap().len(),
        2,
        "runtime trace should include initial and final states"
    );
}

#[test]
fn tp007_artifacts_and_validation_suite() {
    let src = examples_dir().join("planning/ex_005_multi_step.rsn");
    let (ok, stdout) = run_json("run", src.to_str().unwrap());
    assert!(ok, "run command should succeed: {}", stdout);

    let artifact_dir = repo_root().join("artifacts/tp_007");
    for file in &[
        "reason_ir.json",
        "runtime_graph.json",
        "execution_plan.json",
        "inference_result.json",
        "execution_trace.json",
        "validation_report.json",
    ] {
        assert!(
            artifact_dir.join(file).exists(),
            "TP-007 artifact should exist: {}",
            file
        );
    }

    let report: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(artifact_dir.join("validation_report.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(report["passed"].as_bool(), Some(true));
    assert!(
        report["validation_suite"]
            .as_array()
            .unwrap()
            .iter()
            .all(|check| check["status"].as_str() == Some("PASS")),
        "all TP-007 validation suite checks should pass"
    );
}

// ---------------------------------------------------------------------------
// TP-006: 15 examples exist
// ---------------------------------------------------------------------------

#[test]
fn tp006_example_count() {
    let examples = vec![
        "graph/ex_001_minimal_goal.rsn",
        "graph/ex_002_state_transition.rsn",
        "graph/ex_003_taxonomy.rsn",
        "graph/ex_008_concept_graph.rsn",
        "graph/ex_012_deep_taxonomy.rsn",
        "planning/ex_004_navigation.rsn",
        "planning/ex_005_multi_step.rsn",
        "planning/ex_009_planning_module.rsn",
        "planning/ex_013_dbm_planning.rsn",
        "constraint/ex_006_door.rsn",
        "constraint/ex_007_multi_constraint.rsn",
        "constraint/ex_014_context_constraint.rsn",
        "simulation/ex_010_world_model.rsn",
        "simulation/ex_011_event_driven.rsn",
        "simulation/ex_015_attribute_model.rsn",
    ];
    assert!(
        examples.len() >= 10,
        "spec requires at least 10 examples, found {}",
        examples.len()
    );
    for path in &examples {
        let full = examples_dir().join(path);
        assert!(full.exists(), "example file missing: {}", path);
    }
}
