use std::{
    env,
    io::{self, Read},
    path::PathBuf,
};

use reasonscript_cluster_runtime::dynamic::{
    artifacts::validate_dynamic_directory,
    config::DynamicConfig,
    runtime::{plan_dynamic, run_dynamic, DynamicOptions},
    test_model as dynamic_test_model,
};
use reasonscript_cluster_runtime::{
    artifacts::validate_directory,
    config::ClusterConfig,
    evaluator::compare,
    planner::build_cluster_plan,
    runtime::{run_cluster, RunOptions},
    test_model, worker,
    worker::RuntimeContext,
    ReasonTask,
};
use serde_json::Value;

fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}

fn run() -> Result<i32, String> {
    let args: Vec<String> = env::args().skip(1).collect();
    let command = args.first().map(String::as_str).unwrap_or("");
    if command == "verify-native" {
        print_value(
            &serde_json::json!({"ok":true,"profile":"reasonscript-cluster-runtime/0.2","unsafe_blocks":0}),
        )?;
        return Ok(0);
    }
    if command == "dynamic" {
        let subcommand = args.get(1).map(String::as_str).unwrap_or("");
        if subcommand == "validate" {
            let path = args
                .get(2)
                .ok_or("Usage: reason-cluster dynamic validate <artifact-dir>")?;
            let result = validate_dynamic_directory(PathBuf::from(path).as_path());
            print_value(&result)?;
            return Ok(if result["valid"] == true { 0 } else { 1 });
        }
        if subcommand == "test-model" {
            let scenario = option(&args, "--scenario").unwrap_or("dynamic-generation");
            let workers = option(&args, "--workers")
                .and_then(|v| v.parse().ok())
                .unwrap_or(4);
            let result = dynamic_test_model::run(scenario, workers)?;
            print_value(&result)?;
            return Ok(if result["passed"] == true { 0 } else { 1 });
        }
        if !matches!(subcommand, "plan" | "run" | "simulate" | "compare") {
            return Err(
                "Usage: reason-cluster dynamic <plan|run|simulate|validate|compare|test-model>"
                    .into(),
            );
        }
        let envelope = read_stdin_json()?;
        let bundle = &envelope["bundle"];
        let cluster: ClusterConfig = if envelope.get("cluster_config").map_or(true, Value::is_null)
        {
            ClusterConfig::local(
                envelope["workers"].as_u64().unwrap_or(2) as usize,
                "simulation",
            )
        } else {
            serde_json::from_value(envelope["cluster_config"].clone())
                .map_err(|e| format!("CRR-CFG-002: {e}"))?
        };
        let dynamic: DynamicConfig = if envelope.get("dynamic_config").map_or(true, Value::is_null)
        {
            DynamicConfig::default()
        } else {
            serde_json::from_value(envelope["dynamic_config"].clone())
                .map_err(|e| format!("DRU-PRP-001: {e}"))?
        };
        if subcommand == "plan" {
            let result = plan_dynamic(bundle, &cluster, &dynamic);
            print_value(&result)?;
            return Ok(if result["valid"] == true { 0 } else { 1 });
        }
        let artifacts_dir = option(&args, "--artifacts-dir").map(PathBuf::from);
        let result = run_dynamic(
            bundle,
            &cluster,
            &dynamic,
            &DynamicOptions {
                artifacts_dir,
                scenario: None,
            },
        )?;
        let output = if subcommand == "compare" {
            let one = run_dynamic(
                bundle,
                &ClusterConfig::local(1, "simulation"),
                &dynamic,
                &DynamicOptions::default(),
            )?;
            json_compare(&result.summary, &one.summary)
        } else {
            result.summary
        };
        print_value(&output)?;
        return Ok(
            if matches!(output["status"].as_str(), Some("converged" | "completed"))
                || output["equivalent"] == true
            {
                0
            } else {
                1
            },
        );
    }
    if command == "internal-worker" {
        let input = read_stdin_json()?;
        let task: ReasonTask =
            serde_json::from_value(input["task"].clone()).map_err(|e| e.to_string())?;
        let version = input["state_version"].as_u64().unwrap_or(0) as usize;
        println!(
            "{}",
            serde_json::to_string(&worker::execute(
                &task,
                version,
                &serde_json::from_value(input.get("runtime").cloned().unwrap_or(Value::Null))
                    .unwrap_or_default()
            )?)
            .map_err(|e| e.to_string())?
        );
        return Ok(0);
    }
    if command == "validate" {
        let path = args
            .get(1)
            .ok_or("Usage: reason-cluster validate <artifact-dir>")?;
        let result = validate_directory(PathBuf::from(path).as_path());
        print_value(&result)?;
        return Ok(if result["valid"] == true { 0 } else { 1 });
    }
    if command == "test-model" {
        let scenario = option(&args, "--scenario").unwrap_or("independent-parallel");
        let workers = option(&args, "--workers")
            .and_then(|v| v.parse().ok())
            .unwrap_or(4);
        let mode = option(&args, "--mode").unwrap_or("simulation");
        let result = test_model::run(scenario, workers, mode)?;
        print_value(&result)?;
        return Ok(if result["passed"] == true { 0 } else { 1 });
    }
    if !matches!(command, "plan" | "run" | "simulate" | "compare") {
        return Err("Usage: reason-cluster <plan|run|simulate|validate|compare|test-model>".into());
    }
    let envelope = read_stdin_json()?;
    let bundle = &envelope["bundle"];
    let mut config: ClusterConfig = if envelope.get("config").map_or(true, Value::is_null) {
        ClusterConfig::local(
            envelope["workers"].as_u64().unwrap_or(2) as usize,
            if command == "run" {
                "local_process"
            } else {
                "simulation"
            },
        )
    } else {
        serde_json::from_value(envelope["config"].clone())
            .map_err(|e| format!("CRR-CFG-002: {e}"))?
    };
    if command == "simulate" || command == "compare" {
        config.mode = "simulation".into();
    }
    if command == "plan" {
        let payload = bundle.get("artifacts").unwrap_or(bundle);
        let workers: Vec<_> = config.workers.iter().map(|w| w.node_id.clone()).collect();
        let mut plan = build_cluster_plan(
            payload.get("execution_plan").unwrap_or(&Value::Null),
            payload.get("reason_ir").unwrap_or(&Value::Null),
            &workers,
            &config.execution.sync_policy,
        );
        plan.diagnostics.extend(config.validate());
        plan.diagnostics.sort_by(|a, b| a.code.cmp(&b.code));
        plan.valid = plan.diagnostics.iter().all(|d| d.severity != "error");
        let value = serde_json::to_value(plan).map_err(|e| e.to_string())?;
        print_value(&value)?;
        return Ok(if value["valid"] == true { 0 } else { 1 });
    }
    let artifacts_dir = option(&args, "--artifacts-dir").map(PathBuf::from);
    let runtime: RuntimeContext =
        serde_json::from_value(envelope.get("runtime").cloned().unwrap_or(Value::Null))
            .unwrap_or_default();
    let result = run_cluster(
        bundle,
        &config,
        &RunOptions {
            artifacts_dir,
            runtime,
        },
    )?;
    let output = if command == "compare" {
        compare(&result.summary, bundle)
    } else {
        result.summary
    };
    print_value(&output)?;
    Ok(
        if output["status"] == "completed" || output["equivalent"] == true {
            0
        } else {
            1
        },
    )
}

fn read_stdin_json() -> Result<Value, String> {
    let mut text = String::new();
    io::stdin()
        .read_to_string(&mut text)
        .map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| format!("invalid JSON input: {e}"))
}
fn print_value(value: &Value) -> Result<(), String> {
    println!(
        "{}",
        serde_json::to_string_pretty(value).map_err(|e| e.to_string())?
    );
    Ok(())
}
fn option<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.iter()
        .position(|v| v == name)
        .and_then(|i| args.get(i + 1))
        .map(String::as_str)
}
fn json_compare(a: &Value, b: &Value) -> Value {
    let checks = serde_json::json!({"dynamic_units":a["registered_units"]==b["registered_units"],"final_state":a["final_state"]==b["final_state"],"convergence_reason":a["convergence_reason"]==b["convergence_reason"],"semantic_result":a["semantic_result"]==b["semantic_result"]});
    let equivalent = checks
        .as_object()
        .unwrap()
        .values()
        .all(|v| v == &Value::Bool(true));
    serde_json::json!({"schema_version":"reasonscript-dynamic-comparison/0.1","equivalent":equivalent,"checks":checks})
}
