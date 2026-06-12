use reasonscript_hybrid_runtime::ReasonIrValidator;
use std::env;
use std::fs;
use std::process::ExitCode;

fn main() -> ExitCode {
    let paths = env::args().skip(1).collect::<Vec<_>>();
    if paths.is_empty() {
        eprintln!("usage: reason-ir-validator <reason-ir.json>...");
        return ExitCode::from(2);
    }

    let mut failed = false;
    for path in paths {
        match fs::read_to_string(&path) {
            Ok(input) => match ReasonIrValidator::validate_json(&input) {
                Ok(_) => println!("valid: {path}"),
                Err(error) => {
                    eprintln!("invalid: {path}: {error}");
                    failed = true;
                }
            },
            Err(error) => {
                eprintln!("error: {path}: {error}");
                failed = true;
            }
        }
    }

    if failed {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}
