//! `reason-runtime-host` -- versioned ReasonScript execution host.
//!
//! Reads a `reasonscript-runtime-request/1.0` envelope (file path argument,
//! or `-` for stdin), executes its computation IR, and returns a
//! `reasonscript-runtime-result/1.0` envelope. Raw
//! `reason-computation-ir/0.1` remains accepted during migration.
//!
//! ```json
//! {"ok": true, "calculation_results": {"Answer": 3.5}}
//! {"ok": false, "error_code": "RT-ARITH-001", "error_message": "..."}
//! ```
//!
//! This shape is deliberately simple JSON (not the full
//! `reasonscript-integrated-runtime/0.1` envelope the Python side emits)
//! so `frontend.computation_ir`'s differential tests can decode it with
//! plain `json.loads` and compare `calculation_results` against the
//! Python IR interpreter's output for the same program.

use std::env;
use std::fs;
use std::io::{self, Read};
use std::process::ExitCode;

use reasonscript_computation_ir::{decode, to_json, NumericMode, TensorPolicy, Vm};

const REQUEST_SCHEMA: &str = "reasonscript-runtime-request/1.0";
const RESULT_SCHEMA: &str = "reasonscript-runtime-result/1.0";
const HOST_PROFILE: &str = "reasonscript-runtime-host/1.0";

fn main() -> ExitCode {
    let path = env::args().nth(1);
    if path.as_deref() == Some("verify-native") {
        println!(
            "{}",
            serde_json::json!({
                "ok": true,
                "profile": HOST_PROFILE,
                "request_schema": REQUEST_SCHEMA,
                "result_schema": RESULT_SCHEMA,
                "unsafe_blocks": 0,
            })
        );
        return ExitCode::SUCCESS;
    }
    let source = match read_source(path.as_deref()) {
        Ok(source) => source,
        Err(message) => return fail_io(&message),
    };

    let document: serde_json::Value = match serde_json::from_str(&source) {
        Ok(value) => value,
        Err(error) => return fail("IR-DECODE-001", &error.to_string()),
    };
    if document.get("schema").and_then(serde_json::Value::as_str) == Some(REQUEST_SCHEMA) {
        return run_request(&document);
    }

    run_legacy(&source)
}

fn run_legacy(source: &str) -> ExitCode {
    let program = match decode(&source) {
        Ok(program) => program,
        Err(error) => return fail("IR-DECODE-001", &error.to_string()),
    };

    let vm = Vm::with_numeric_mode(&program, numeric_mode_from_env());
    match vm.run_calculations(&program) {
        Ok(calculations) => {
            let mut results = serde_json::Map::new();
            for (name, value) in calculations {
                results.insert(name, to_json(&value));
            }
            let payload = serde_json::json!({
                "ok": true,
                "calculation_results": results,
            });
            println!("{payload}");
            ExitCode::SUCCESS
        }
        Err(error) => fail(&error.code, &error.message),
    }
}

fn run_request(request: &serde_json::Value) -> ExitCode {
    let request_id = request
        .get("request_id")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    if request_id.is_empty() {
        return fail_request(
            request_id,
            "RTH-PROTO-001",
            "runtime request_id must be a non-empty string",
        );
    }
    if request.get("operation").and_then(serde_json::Value::as_str) != Some("execute") {
        return fail_request(
            request_id,
            "RTH-PROTO-002",
            "runtime request operation must be execute",
        );
    }
    let Some(program_value) = request.get("program") else {
        return fail_request(
            request_id,
            "RTH-PROTO-003",
            "runtime request program is required",
        );
    };
    let Some(context) = request
        .get("context")
        .and_then(serde_json::Value::as_object)
    else {
        return fail_request(
            request_id,
            "RTH-PROTO-003",
            "runtime request context is required",
        );
    };
    if !context
        .get("capabilities")
        .is_some_and(serde_json::Value::is_object)
        || !context
            .get("limits")
            .is_some_and(serde_json::Value::is_object)
        || !context
            .get("trace")
            .is_some_and(serde_json::Value::is_object)
        || !context
            .get("resource_root")
            .is_some_and(serde_json::Value::is_string)
    {
        return fail_request(
            request_id,
            "RTH-PROTO-003",
            "runtime request context is malformed",
        );
    }
    let source = match serde_json::to_string(program_value) {
        Ok(value) => value,
        Err(error) => return fail_request(request_id, "RTH-PROTO-003", &error.to_string()),
    };
    let program = match decode(&source) {
        Ok(program) => program,
        Err(error) => return fail_request(request_id, "IR-DECODE-001", &error.to_string()),
    };
    let numeric_mode_name = request
        .pointer("/context/numeric_mode")
        .and_then(serde_json::Value::as_str);
    if !matches!(numeric_mode_name, Some("compat-reference" | "native-fast")) {
        return fail_request(
            request_id,
            "RTH-PROTO-004",
            "numeric_mode must be compat-reference or native-fast",
        );
    }
    let numeric_mode = numeric_mode_from_name(numeric_mode_name.unwrap_or("compat-reference"));
    let limits = context
        .get("limits")
        .and_then(serde_json::Value::as_object)
        .unwrap();
    let mut tensor_policy = TensorPolicy::default();
    tensor_policy.max_rank = limit(limits, "max_rank", tensor_policy.max_rank);
    tensor_policy.max_elements = limit(limits, "max_elements", tensor_policy.max_elements);
    tensor_policy.max_tensor_bytes =
        limit(limits, "max_tensor_bytes", tensor_policy.max_tensor_bytes);
    tensor_policy.max_live_tensors =
        limit(limits, "max_live_tensors", tensor_policy.max_live_tensors);
    tensor_policy.max_shape_dimension = limit(
        limits,
        "max_shape_dimension",
        tensor_policy.max_shape_dimension,
    );
    tensor_policy.max_artifact_bytes = limit(
        limits,
        "max_artifact_bytes",
        tensor_policy.max_artifact_bytes,
    );
    tensor_policy.inline_elements = limit(limits, "inline_elements", tensor_policy.inline_elements);
    tensor_policy.max_autograd_nodes = limit(
        limits,
        "max_autograd_nodes",
        tensor_policy.max_autograd_nodes,
    );
    tensor_policy.max_saved_tensor_bytes = limit(
        limits,
        "max_saved_tensor_bytes",
        tensor_policy.max_saved_tensor_bytes,
    );
    let capabilities = context
        .get("capabilities")
        .and_then(serde_json::Value::as_object)
        .unwrap();
    let filesystem_read = capabilities
        .get("filesystem_read")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false);
    let filesystem_write = capabilities
        .get("filesystem_write")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false);
    let trace_enabled = request
        .pointer("/context/trace/enabled")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false);
    let resource_root = std::path::PathBuf::from(
        context
            .get("resource_root")
            .and_then(serde_json::Value::as_str)
            .unwrap(),
    );
    let vm = Vm::with_runtime_context(
        &program,
        numeric_mode,
        tensor_policy,
        resource_root,
        filesystem_read,
        filesystem_write,
        trace_enabled,
    );
    match vm.run_calculations(&program) {
        Ok(calculations) => {
            let loop_trace = vm.loop_trace();
            let tensor_trace = vm.tensor_trace();
            let vision_trace = vm.vision_trace();
            let tensor_metadata = vm.tensor_metadata();
            let mut combined_trace = loop_trace.clone();
            combined_trace.extend(tensor_trace.clone());
            combined_trace.extend(vision_trace.clone());
            let mut results = serde_json::Map::new();
            for (name, value) in calculations {
                results.insert(name, to_json(&value));
            }
            println!(
                "{}",
                serde_json::json!({
                    "schema": RESULT_SCHEMA,
                    "request_id": request_id,
                    "ok": true,
                    "execution_mode": "rust",
                    "calculation_results": results,
                    "diagnostics": [],
                    "metadata": {
                        "host_profile": HOST_PROFILE,
                        "trace": combined_trace,
                        "loop_trace": loop_trace,
                        "tensor_trace": tensor_trace,
                        "vision_trace": vision_trace,
                        "tensor_metadata": tensor_metadata,
                        "reason_object_metadata": [],
                    },
                })
            );
            ExitCode::SUCCESS
        }
        Err(error) => fail_runtime_request(request_id, &error),
    }
}

fn limit(limits: &serde_json::Map<String, serde_json::Value>, name: &str, default: usize) -> usize {
    limits
        .get(name)
        .and_then(serde_json::Value::as_u64)
        .and_then(|value| usize::try_from(value).ok())
        .unwrap_or(default)
}

fn numeric_mode_from_name(name: &str) -> NumericMode {
    match name {
        "native-fast" => NumericMode::NativeFast,
        _ => NumericMode::CompatReference,
    }
}

/// Phase 9: `REASONSCRIPT_NUMERIC_MODE=native-fast` opts into real `f32`
/// rounding and the parallel/rayon op paths (see `NumericMode`'s doc
/// comment). Any other value (including unset) keeps the default,
/// unchanged `CompatReference` behavior -- mirrors the
/// `REASONSCRIPT_SHADOW_MODE` env-var precedent from Phase 6
/// (`scripts/reason_cli.py`), not a new pattern.
fn numeric_mode_from_env() -> NumericMode {
    match env::var("REASONSCRIPT_NUMERIC_MODE").as_deref() {
        Ok("native-fast") => NumericMode::NativeFast,
        _ => NumericMode::CompatReference,
    }
}

fn read_source(path: Option<&str>) -> Result<String, String> {
    match path {
        None | Some("-") => {
            let mut buffer = String::new();
            io::stdin()
                .read_to_string(&mut buffer)
                .map_err(|error| error.to_string())?;
            Ok(buffer)
        }
        Some(path) => fs::read_to_string(path).map_err(|error| format!("{path}: {error}")),
    }
}

fn fail(code: &str, message: &str) -> ExitCode {
    let payload = serde_json::json!({
        "ok": false,
        "error_code": code,
        "error_message": message,
    });
    println!("{payload}");
    ExitCode::FAILURE
}

fn fail_io(message: &str) -> ExitCode {
    fail("IR-IO-001", message)
}

fn fail_request(request_id: &str, code: &str, message: &str) -> ExitCode {
    fail_request_with_location(request_id, code, message, None)
}

fn fail_runtime_request(
    request_id: &str,
    error: &reasonscript_computation_ir::RuntimeError,
) -> ExitCode {
    fail_request_with_location(
        request_id,
        &error.code,
        &error.message,
        error.source_location.clone(),
    )
}

fn fail_request_with_location(
    request_id: &str,
    code: &str,
    message: &str,
    source_location: Option<serde_json::Value>,
) -> ExitCode {
    let payload = serde_json::json!({
        "schema": RESULT_SCHEMA,
        "request_id": request_id,
        "ok": false,
        "execution_mode": "rust",
        "calculation_results": null,
        "diagnostics": [{
            "code": code,
            "severity": "error",
            "category": "runtime",
            "message": message,
            "source_location": source_location,
        }],
        "metadata": {
            "host_profile": HOST_PROFILE,
            "trace": [],
            "tensor_metadata": [],
            "reason_object_metadata": [],
        },
    });
    println!("{payload}");
    ExitCode::FAILURE
}
