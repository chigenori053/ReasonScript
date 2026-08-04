use super::{
    config::DynamicConfig,
    runtime::{run_dynamic, DynamicOptions},
};
use crate::{canonical::checksum, config::ClusterConfig, test_model};
use serde_json::{json, Value};

pub const SCENARIOS: [&str; 14] = [
    "dynamic-generation",
    "multi-generation",
    "duplicate-elimination",
    "generation-depth-limit",
    "suspension-reactivation",
    "replacement",
    "dynamic-dependency",
    "branch-pruning",
    "convergence",
    "budget-termination",
    "worker-failure",
    "determinism",
    "worker-count-equivalence",
    "molecular-dynamic",
];

pub fn run(scenario: &str, workers: usize) -> Result<Value, String> {
    if !SCENARIOS.contains(&scenario) {
        return Err(format!(
            "unknown Dynamic ReasonUnit TestModel scenario: {scenario}"
        ));
    }
    let base = if scenario == "molecular-dynamic" {
        "molecular-partition"
    } else {
        "dependency-chain"
    };
    let bundle = test_model::bundle(base)?;
    if scenario == "determinism" {
        let mut results = Vec::new();
        for _ in 0..3 {
            results.push(execute(&bundle, scenario, workers)?.summary);
        }
        let digests: Vec<_> = results
            .iter()
            .map(|v| checksum(v).unwrap_or_default())
            .collect();
        return Ok(
            json!({"schema_version":"reasonscript-dynamic-test-model-result/0.1","scenario":"DRU-TM-012","passed":digests.windows(2).all(|x|x[0]==x[1]),"canonical_digests":digests,"runs":results}),
        );
    }
    if scenario == "worker-count-equivalence" {
        let mut results = Vec::new();
        for n in [1, 2, 4] {
            results.push(execute(&bundle, scenario, n)?.summary);
        }
        let semantic:Vec<_>=results.iter().map(|v|checksum(&json!({"units":v["registered_units"],"final_state":v["final_state"],"reason":v["convergence_reason"]})).unwrap_or_default()).collect();
        return Ok(
            json!({"schema_version":"reasonscript-dynamic-test-model-result/0.1","scenario":"DRU-TM-013","passed":semantic.windows(2).all(|x|x[0]==x[1]),"semantic_digests":semantic,"runs":results}),
        );
    }
    let result = execute(&bundle, scenario, workers)?;
    let proposals = &result.documents["dynamic_unit_proposals.jsonl"];
    let lifecycle = &result.documents["dynamic_unit_lifecycle.jsonl"];
    let diagnostics = &result.summary["diagnostics"];
    let passed = match scenario {
        "dynamic-generation" => {
            result.summary["generated_units"] == 1 && has_state(lifecycle, "completed")
        }
        "multi-generation" => result.summary["generated_units"] == 3,
        "duplicate-elimination" => {
            result.summary["generated_units"] == 1
                && proposals.as_array().map_or(false, |a| {
                    a.iter().any(|p| p["diagnostic"] == "DRU-PRP-006")
                })
        }
        "generation-depth-limit" => has_diag(diagnostics, "DRU-GEN-002"),
        "suspension-reactivation" => {
            has_reason(lifecycle, "dependency_missing")
                && has_reason(lifecycle, "dependency_satisfied")
        }
        "replacement" => has_state(lifecycle, "replaced"),
        "dynamic-dependency" => result.documents["dynamic_plan_revisions.jsonl"]
            .as_array()
            .map_or(false, |a| {
                a.iter().all(|r| r["atomic"] == true)
                    && a.iter().any(|r| {
                        r["dependency_updates"]
                            .as_array()
                            .map_or(false, |x| !x.is_empty())
                    })
            }),
        "branch-pruning" => result.summary["pruned_branches"] == 1,
        "convergence" => {
            result.summary["status"] == "converged"
                && result.documents["dynamic_convergence_report.json"]["global_convergence"] == true
        }
        "budget-termination" => {
            result.summary["status"] == "budget_terminated"
                && result.documents["dynamic_budget_report.json"]["terminated"] == true
        }
        "worker-failure" => {
            has_reason(lifecycle, "worker_failure") && has_reason(lifecycle, "retry_repartition")
        }
        "molecular-dynamic" => result.documents["dynamic_branch_graph.json"]["units"]
            .as_array()
            .map_or(false, |a| {
                a.iter().any(|u| u["unit_kind"] == "boundary_interaction")
            }),
        _ => false,
    };
    Ok(
        json!({"schema_version":"reasonscript-dynamic-test-model-result/0.1","scenario":id(scenario),"passed":passed,"run":result.summary,"artifact_validation":super::artifacts::validate_documents(&result.documents)}),
    )
}
fn execute(
    bundle: &Value,
    scenario: &str,
    workers: usize,
) -> Result<super::runtime::DynamicRun, String> {
    let cluster = ClusterConfig::local(workers, "simulation");
    let mut config = DynamicConfig::default();
    if scenario == "generation-depth-limit" {
        config.limits.max_generation_depth = 3;
    }
    if scenario == "budget-termination" {
        config.limits.max_total_units = 3;
    }
    run_dynamic(
        bundle,
        &cluster,
        &config,
        &DynamicOptions {
            artifacts_dir: None,
            scenario: Some(scenario.into()),
        },
    )
}
fn has_diag(v: &Value, code: &str) -> bool {
    v.as_array()
        .map_or(false, |a| a.iter().any(|x| x["code"] == code))
}
fn has_state(v: &Value, state: &str) -> bool {
    v.as_array()
        .map_or(false, |a| a.iter().any(|x| x["to"] == state))
}
fn has_reason(v: &Value, reason: &str) -> bool {
    v.as_array()
        .map_or(false, |a| a.iter().any(|x| x["reason"] == reason))
}
fn id(s: &str) -> &str {
    match s {
        "dynamic-generation" => "DRU-TM-001",
        "multi-generation" => "DRU-TM-002",
        "duplicate-elimination" => "DRU-TM-003",
        "generation-depth-limit" => "DRU-TM-004",
        "suspension-reactivation" => "DRU-TM-005",
        "replacement" => "DRU-TM-006",
        "dynamic-dependency" => "DRU-TM-007",
        "branch-pruning" => "DRU-TM-008",
        "convergence" => "DRU-TM-009",
        "budget-termination" => "DRU-TM-010",
        "worker-failure" => "DRU-TM-011",
        "molecular-dynamic" => "DRU-TM-MOL-001",
        _ => "DRU-TM-UNKNOWN",
    }
}
