use serde_json::{json, Value};

use crate::{
    canonical::canonical_json,
    config::{ClusterConfig, TestingConfig},
    runtime::{run_cluster, RunOptions},
};

pub const SCENARIOS: [&str; 9] = [
    "independent-parallel",
    "dependency-chain",
    "fan-out-fan-in",
    "state-conflict",
    "worker-failure",
    "determinism",
    "single-node-equivalence",
    "fallback",
    "molecular-partition",
];

pub fn bundle(scenario: &str) -> Result<Value, String> {
    let units: Vec<(&str, &str, Vec<&str>)> = match scenario {
        "dependency-chain" => vec![
            ("Start", "A", vec![]),
            ("A", "B", vec![]),
            ("B", "C", vec![]),
        ],
        "fan-out-fan-in" => vec![
            ("Start", "A", vec![]),
            ("A", "B", vec![]),
            ("A", "C", vec![]),
            ("B", "D", vec!["C"]),
        ],
        "molecular-partition" => vec![
            ("Molecule", "RegionA", vec![]),
            ("Molecule", "RegionB", vec![]),
            ("RegionA", "Boundary", vec!["RegionB"]),
            ("Boundary", "Global", vec![]),
        ],
        value if SCENARIOS.contains(&value) => vec![
            ("Start", "A", vec![]),
            ("Start", "B", vec![]),
            ("Start", "C", vec![]),
        ],
        _ => return Err(format!("unknown Cluster TestModel scenario: {scenario}")),
    };
    let mut steps = Vec::new();
    let mut transitions = Vec::new();
    let mut knowledge = Vec::new();
    for (index, (source, target, extras)) in units.iter().enumerate() {
        let transition_id = format!("unit-{target}-{}", index + 1);
        let step = json!({"step_id":format!("step-{}",index+1),"transition_id":transition_id,"source":source,"target":target});
        let writes = if scenario == "state-conflict" {
            json!(["shared.non_commutative"])
        } else {
            json!([target])
        };
        let mut inputs = vec![*source];
        inputs.extend(extras.iter().copied());
        transitions.push(json!({"transition_id":transition_id,"source":source,"target":target,"effect":{"inputs":inputs},"cluster_policy":{"deterministic":true,"retriable":true,"state_access":{"read":[source],"write":writes}}}));
        steps.push(step);
        knowledge.push(json!({"id":format!("K{:03}",index+1),"source":source,"target":target}));
    }
    let final_state = units.last().unwrap().1;
    Ok(
        json!({"ok":true,"source_file":format!("cluster-test-model:{scenario}"),"diagnostics":[],"artifacts":{"execution_plan":{"schema_version":"execution-plan/0.1","selected_steps":steps,"alternative_paths":[],"expected_cost":units.len(),"evidence_refs":[],"planner_version":"cluster-test-model/0.1","goal":final_state},"reason_ir":{"schema_version":"reason-ir/0.1","transitions":transitions},"simulation":{"schema_version":"semantic-simulation/0.2","success":true,"goal_reached":true,"final_state":final_state,"step_count":units.len(),"trace":[]},"knowledge":{"schema_version":"knowledge-emergence/0.2","knowledge":knowledge}}}),
    )
}

pub fn run(scenario: &str, workers: usize, mode: &str) -> Result<Value, String> {
    let model = bundle(scenario)?;
    let mut config = ClusterConfig::local(workers, mode);
    if scenario == "worker-failure" {
        config.testing = Some(TestingConfig {
            fail_task_once: Some("task_0001".into()),
        });
    }
    if scenario == "fallback" {
        config.workers.clear();
    }
    if scenario == "determinism" {
        let runs: Vec<_> = (0..3)
            .map(|_| run_cluster(&model, &config, &RunOptions::default()).map(|r| r.summary))
            .collect::<Result<_, _>>()?;
        let deterministic = runs
            .windows(2)
            .all(|p| canonical_json(&p[0]).ok() == canonical_json(&p[1]).ok());
        return Ok(
            json!({"schema_version":"reasonscript-cluster-test-model-result/0.1","scenario":"CRR-TM-006","passed":deterministic&&runs[0]["status"]=="completed","runs":runs}),
        );
    }
    let result = run_cluster(&model, &config, &RunOptions::default())?;
    let diagnostics = &result.documents["cluster_diagnostics.json"]["diagnostics"];
    let passed = match scenario {
        "state-conflict" => {
            result.summary["status"] == "failed"
                && diagnostics
                    .as_array()
                    .unwrap()
                    .iter()
                    .any(|d| d["code"] == "CRR-PLN-006")
        }
        "worker-failure" => {
            result.summary["status"] == "completed"
                && result.documents["cluster_evaluation_report.json"]["efficiency"]["retry_count"]
                    == 1
        }
        "fallback" => {
            result.summary["status"] == "completed" && result.summary["fallback_used"] == true
        }
        _ => {
            result.summary["status"] == "completed"
                && result.documents["cluster_evaluation_report.json"]["passed"] == true
        }
    };
    let id = match scenario {
        "independent-parallel" => "CRR-TM-001",
        "dependency-chain" => "CRR-TM-002",
        "fan-out-fan-in" => "CRR-TM-003",
        "state-conflict" => "CRR-TM-004",
        "worker-failure" => "CRR-TM-005",
        "single-node-equivalence" => "CRR-TM-007",
        "fallback" => "CRR-TM-008",
        "molecular-partition" => "CRR-TM-MOL-001",
        _ => "CRR-TM-006",
    };
    Ok(
        json!({"schema_version":"reasonscript-cluster-test-model-result/0.1","scenario":id,"passed":passed,"run":result.summary,"diagnostics":diagnostics}),
    )
}
