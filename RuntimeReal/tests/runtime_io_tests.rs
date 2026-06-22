use reasonscript_runtime_real::runtime_io::{
    input_operation, print_operation, ProjectionPolicy, RuntimeIo,
};
use serde_json::json;

#[test]
fn rio_001_input_creates_input_state() {
    let state = RuntimeIo::input(json!(20));

    assert_eq!(state.state_id, "Input1");
    assert_eq!(state.state_type, "Input");
    assert_eq!(state.value, json!(20));
}

#[test]
fn rio_002_primitive_input_preserves_json_value() {
    let operation = input_operation(json!(42));

    assert_eq!(operation["operation"], "input");
    assert_eq!(operation["state"]["state_type"], "Input");
    assert_eq!(operation["state"]["value"], json!(42));
}

#[test]
fn rio_003_structured_input_preserves_json_value() {
    let state = RuntimeIo::input(json!({"name": "Alice"}));

    assert_eq!(state.state_type, "Input");
    assert_eq!(state.value, json!({"name": "Alice"}));
}

#[test]
fn rio_004_print_state_generates_output_event_without_state_delta() {
    let state = json!({
        "state_id": "Input1",
        "state_type": "Input",
        "value": 20
    });
    let operation = print_operation("Input1", &state);

    assert_eq!(operation["operation"], "print");
    assert_eq!(operation["source_state"], "Input1");
    assert_eq!(operation["output_event"]["projection"], "canonical");
    assert!(operation["state_delta"].is_null());
}

#[test]
fn rio_005_print_knowledge_uses_canonical_projection() {
    let knowledge = json!({
        "relation": "IsA",
        "confidence": 0.98,
        "evidence": []
    });
    let event = RuntimeIo::print_state("knowledge", &knowledge);

    assert_eq!(event.rendered_value, knowledge);
}

#[test]
fn rio_006_equal_state_and_projection_produce_equal_output_event() {
    let state = json!({"state_id": "S1", "state_type": "Input", "value": true});

    let first = RuntimeIo::project("S1", &state, ProjectionPolicy::Canonical);
    let second = RuntimeIo::project("S1", &state, ProjectionPolicy::Canonical);

    assert_eq!(first, second);
}
