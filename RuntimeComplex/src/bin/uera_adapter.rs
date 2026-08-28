use serde_json::{json, Value};
use std::io::{self, Read};

fn main() {
    let operation = std::env::args().nth(1).unwrap_or_default();
    if operation != "uera-execute" {
        fail("UER-REQ-001: uera-execute is required");
    }
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        fail("UER-REQ-003: unable to read execution request");
    }
    let request: Value = serde_json::from_str(&input)
        .unwrap_or_else(|_| fail("UER-REQ-003: invalid execution request JSON"));
    let request_id = request
        .get("request_id")
        .and_then(Value::as_str)
        .unwrap_or_else(|| fail("UER-REQ-003: request_id is required"));
    let plan = request
        .get("execution_plan")
        .unwrap_or_else(|| fail("UER-REQ-003: execution_plan is required"));
    if plan.get("operation").and_then(Value::as_str) != Some("identity") {
        fail("UER-REQ-001: unsupported operation");
    }
    let arguments = plan
        .get("arguments")
        .and_then(Value::as_array)
        .filter(|items| items.len() == 1)
        .unwrap_or_else(|| fail("UER-REQ-002: identity requires exactly one argument"));
    println!(
        "{}",
        json!({"ok": true, "request_id": request_id, "value": arguments[0]})
    );
}

fn fail(message: &str) -> ! {
    println!("{}", json!({"ok": false, "diagnostics": [message]}));
    std::process::exit(1)
}
