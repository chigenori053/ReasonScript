use reasonscript_dto::ReasonIR;
use std::{env, fs, process};

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: conformance_adapter <reason-ir.json>");
        process::exit(2);
    });
    let input = fs::read_to_string(path).unwrap_or_else(|error| {
        eprintln!("{error}");
        process::exit(2);
    });
    match ReasonIR::from_json(&input) {
        Ok(ir) => println!(
            "{}",
            serde_json::to_string(&ir).expect("serialize ReasonIR")
        ),
        Err(error) => {
            eprintln!("{error}");
            process::exit(1);
        }
    }
}
