use std::{env, fs};

fn main() {
    let path = env::args().nth(1).expect("fixture path is required");
    let source = fs::read_to_string(path).expect("fixture must be readable");
    let output =
        reasonscript_ast_dto::round_trip_json(&source).expect("fixture must be valid AST JSON");
    println!("{output}");
}
