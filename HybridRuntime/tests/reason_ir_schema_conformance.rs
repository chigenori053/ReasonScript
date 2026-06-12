use reasonscript_hybrid_runtime::{
    ReasonIR, ReasonIrError, ReasonIrValidator, REASON_IR_SCHEMA_ID, REASON_IR_VERSION,
};
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}

fn fixture(kind: &str, name: &str) -> String {
    fs::read_to_string(repository_root().join("fixtures").join(kind).join(name)).unwrap()
}

#[test]
fn schema_has_the_versioned_contract_identity_and_required_fields() {
    let schema_text =
        fs::read_to_string(repository_root().join("schemas/reason_ir.schema.json")).unwrap();
    let schema: Value = serde_json::from_str(&schema_text).unwrap();

    assert_eq!(schema["$id"], REASON_IR_SCHEMA_ID);
    assert_eq!(
        schema["properties"]["schema_version"]["const"],
        REASON_IR_VERSION
    );
    assert_eq!(
        schema["required"],
        json!([
            "schema_version",
            "initial_state",
            "goal",
            "transitions",
            "execution_policy",
            "trace_policy"
        ])
    );
    assert_eq!(
        schema["$defs"]["transition_spec"]["properties"]["expected_cost"]["minimum"],
        0
    );
}

#[test]
fn every_valid_fixture_validates_and_round_trips() {
    for name in [
        "dog_to_animal.json",
        "constraint_pass.json",
        "constraint_fail.json",
        "tool_integration.json",
        "worldmodel_transition.json",
    ] {
        let input = fixture("valid", name);
        let ir = ReasonIrValidator::validate_json(&input)
            .unwrap_or_else(|error| panic!("{name} should be valid: {error}"));
        let encoded = ir.to_json_pretty().unwrap();
        let restored = ReasonIR::from_json(&encoded).unwrap();
        assert_eq!(restored, ir, "{name} failed round-trip");
    }
}

#[test]
fn every_invalid_fixture_is_rejected() {
    for name in [
        "missing_goal.json",
        "duplicate_transition_id.json",
        "negative_cost.json",
        "invalid_version.json",
    ] {
        let input = fixture("invalid", name);
        assert!(
            ReasonIrValidator::validate_json(&input).is_err(),
            "{name} should be invalid"
        );
    }
}

#[test]
fn unknown_and_unversioned_documents_are_rejected() {
    let valid = fixture("valid", "dog_to_animal.json");
    let mut value: Value = serde_json::from_str(&valid).unwrap();
    value["schema_version"] = json!("reason-ir/0.2");
    assert_eq!(
        ReasonIrValidator::validate_value(value),
        Err(ReasonIrError::UnsupportedVersion(
            "reason-ir/0.2".to_string()
        ))
    );

    let mut unversioned: Value = serde_json::from_str(&valid).unwrap();
    unversioned
        .as_object_mut()
        .unwrap()
        .remove("schema_version");
    assert_eq!(
        ReasonIrValidator::validate_value(unversioned),
        Err(ReasonIrError::MissingField("schema_version".to_string()))
    );
}

#[test]
fn invalid_uri_and_unknown_fields_are_rejected() {
    let valid = fixture("valid", "tool_integration.json");
    let mut invalid_uri: Value = serde_json::from_str(&valid).unwrap();
    invalid_uri["context_refs"][0]["uri"] = json!("not a uri");
    assert!(matches!(
        ReasonIrValidator::validate_value(invalid_uri),
        Err(ReasonIrError::InvalidField(field)) if field.starts_with("context.uri:")
    ));

    let mut unknown_field: Value = serde_json::from_str(&valid).unwrap();
    unknown_field["runtime_object"] = json!("must not cross the ABI");
    assert!(matches!(
        ReasonIrValidator::validate_value(unknown_field),
        Err(ReasonIrError::Serialization(_))
    ));
}
