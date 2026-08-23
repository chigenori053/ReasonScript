//! `reason-computation-runtime` -- Phase 3 primitive execution CLI.
//!
//! Reads a `reason-computation-ir/0.1` JSON document (file path argument,
//! or `-` for stdin), executes every calculation in it via the
//! Tensor-less VM, and prints a JSON result to stdout:
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

use reasonscript_computation_ir::{decode, to_json, Vm};

fn main() -> ExitCode {
    let path = env::args().nth(1);
    let source = match read_source(path.as_deref()) {
        Ok(source) => source,
        Err(message) => return fail_io(&message),
    };

    let program = match decode(&source) {
        Ok(program) => program,
        Err(error) => return fail("IR-DECODE-001", &error.to_string()),
    };

    let vm = Vm::new(&program);
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
