//! In-process dispatch for the complete `ruo.*` runtime namespace.

use std::cell::RefCell;
use std::collections::{BTreeSet, HashSet};
use std::path::Component;
use std::rc::Rc;

use reasonscript_native_reasonunit_runtime::NativeReasonUnitObject;
use serde_json::{json, Value as JsonValue};
use sha2::{Digest, Sha256};

use crate::value::{RuntimeReasonObjectSnapshot, RuntimeReasonTransaction, Value};
use crate::vm::RuntimeError;

type Result<T> = std::result::Result<T, RuntimeError>;

pub fn call(function_id: &str, arguments: Vec<Value>) -> Result<Value> {
    match function_id {
        "ruo.status" => status(arguments.first()),
        "ruo.diagnostics" => Ok(Value::Array(Rc::new(RefCell::new(Vec::new())))),
        "ruo.object_id" => {
            let snapshot = snapshot(argument(&arguments, 0)?)?;
            Ok(Value::String(Rc::from(snapshot.object.object_id.as_str())))
        }
        "ruo.snapshot" => Ok(Value::ReasonObjectSnapshot(snapshot(argument(
            &arguments, 0,
        )?)?)),
        "ruo.resolve" => resolve(&arguments),
        "ruo.query" => query(&arguments),
        "ruo.begin" => Ok(Value::ReasonTransaction(transaction(argument(
            &arguments, 0,
        )?)?)),
        "ruo.apply" => apply(&arguments),
        "ruo.validate" => validate(&arguments),
        "ruo.commit" => commit(&arguments),
        "ruo.rollback" => rollback(&arguments),
        "ruo.select" => select(&arguments, false),
        "ruo.materialize" => select(&arguments, true),
        "ruo.project" => project(&arguments),
        "ruo.save" => save(&arguments),
        "ruo.tensor_view" => tensor_view(&arguments),
        _ => Err(error(format!(
            "unknown ruo standard function: {function_id}"
        ))),
    }
}

fn argument(arguments: &[Value], index: usize) -> Result<&Value> {
    arguments
        .get(index)
        .ok_or_else(|| error("missing ruo argument"))
}

fn snapshot(value: &Value) -> Result<Rc<RuntimeReasonObjectSnapshot>> {
    match value {
        Value::ReasonObject(owner) => Ok(Rc::new(RuntimeReasonObjectSnapshot {
            object: owner.object.borrow().clone(),
            owner: owner.clone(),
        })),
        Value::ReasonObjectSnapshot(snapshot) => Ok(snapshot.clone()),
        other => Err(error(format!(
            "operation requires ReasonObject or ReasonObjectSnapshot, got {}",
            other.type_name()
        ))),
    }
}

fn transaction(value: &Value) -> Result<Rc<RefCell<RuntimeReasonTransaction>>> {
    if let Value::ReasonTransaction(transaction) = value {
        if transaction.borrow().closed {
            return Err(RuntimeError::new(
                "RUO-N2-015",
                "transaction is already closed",
            ));
        }
        return Ok(transaction.clone());
    }
    Ok(Rc::new(RefCell::new(RuntimeReasonTransaction {
        snapshot: snapshot(value)?,
        operations: Vec::new(),
        closed: false,
    })))
}

fn json_object(value: &Value, label: &str) -> Result<serde_json::Map<String, JsonValue>> {
    let decoded = match value {
        Value::Json(value) => (**value).clone(),
        Value::String(value) => serde_json::from_str(value)
            .map_err(|_| error(format!("{label} must be canonical JSON")))?,
        other => crate::value::to_json(other),
    };
    decoded
        .as_object()
        .cloned()
        .ok_or_else(|| error(format!("{label} must be an object")))
}

fn resolve(arguments: &[Value]) -> Result<Value> {
    let snapshot = snapshot(argument(arguments, 0)?)?;
    let stable_id = string(argument(arguments, 1)?, "ruo.resolve requires StableId")?;
    Ok(resolve_logical(&snapshot.object.logical, &stable_id)
        .map(|value| Value::Json(Rc::new(value)))
        .unwrap_or(Value::Null))
}

fn resolve_logical(logical: &JsonValue, stable_id: &str) -> Option<JsonValue> {
    if logical
        .pointer("/object_identity/entity_id")
        .and_then(JsonValue::as_str)
        == Some(stable_id)
    {
        return logical.get("object_identity").cloned();
    }
    for registry in [
        "units",
        "payloads",
        "states",
        "relations",
        "constraints",
        "evidence_registry",
        "projection_descriptors",
        "revisions",
    ] {
        for item in logical
            .get(registry)
            .and_then(JsonValue::as_array)
            .into_iter()
            .flatten()
        {
            if id_keys()
                .iter()
                .any(|key| item.get(key).and_then(JsonValue::as_str) == Some(stable_id))
            {
                return Some(item.clone());
            }
        }
    }
    None
}

fn query(arguments: &[Value]) -> Result<Value> {
    let snapshot = snapshot(argument(arguments, 0)?)?;
    let spec = json_object(argument(arguments, 1)?, "ReasonQuery")?;
    let name = spec
        .get("query")
        .or_else(|| spec.get("profile"))
        .and_then(JsonValue::as_str)
        .unwrap_or("");
    let argument = spec.get("argument").and_then(JsonValue::as_str);
    let logical = &snapshot.object.logical;
    let result = match name {
        "all" => json!({"entity_ids": entity_ids(logical).into_iter().collect::<Vec<_>>()}),
        "entity_by_id" => argument
            .and_then(|id| resolve_logical(logical, id))
            .unwrap_or(JsonValue::Null),
        "owner" => argument
            .and_then(|id| resolve_logical(logical, id))
            .and_then(|item| {
                item.get("owner_object_id")
                    .or_else(|| item.get("owner_id"))
                    .cloned()
            })
            .unwrap_or(JsonValue::Null),
        "children" => JsonValue::Array(
            logical
                .get("units")
                .and_then(JsonValue::as_array)
                .into_iter()
                .flatten()
                .find(|item| item.get("entity_id").and_then(JsonValue::as_str) == argument)
                .and_then(|item| item.get("children").and_then(JsonValue::as_array))
                .cloned()
                .unwrap_or_default(),
        ),
        "payloads_by_owner" => sorted_registry(logical, "payloads", "payload_id", |item| {
            item.get("owner_id").and_then(JsonValue::as_str) == argument
        }),
        "supporting_evidence" => {
            sorted_registry(logical, "evidence_registry", "evidence_id", |item| {
                item.get("supports")
                    .and_then(JsonValue::as_array)
                    .is_some_and(|items| items.iter().any(|item| item.as_str() == argument))
            })
        }
        "execution_eligible_units" => JsonValue::Array(
            eligible_units(logical)
                .into_iter()
                .map(JsonValue::String)
                .collect(),
        ),
        "knowledge_status" => knowledge_status(logical, argument),
        "extensions" => sorted_registry(logical, "extension_registry", "namespace", |item| {
            argument.is_none() || item.get("namespace").and_then(JsonValue::as_str) == argument
        }),
        "invalidation_closure" => JsonValue::Array(
            dependency_closure(logical, argument.into_iter(), true)
                .into_iter()
                .map(JsonValue::String)
                .collect(),
        ),
        _ => {
            return Err(RuntimeError::new(
                "RUO-N2-014",
                format!("unknown universal query: {name}"),
            ))
        }
    };
    Ok(Value::Json(Rc::new(result)))
}

fn apply(arguments: &[Value]) -> Result<Value> {
    let transaction = transaction(argument(arguments, 0)?)?;
    let operation = JsonValue::Object(json_object(argument(arguments, 1)?, "ReasonOperation")?);
    transaction.borrow_mut().operations.push(operation);
    Ok(Value::ReasonTransaction(transaction))
}

fn candidate(transaction: &RuntimeReasonTransaction) -> JsonValue {
    let mut logical = transaction.snapshot.object.logical.clone();
    for operation in &transaction.operations {
        let Some(updates) = operation
            .get("state_updates")
            .and_then(JsonValue::as_object)
        else {
            continue;
        };
        for state in logical
            .get_mut("states")
            .and_then(JsonValue::as_array_mut)
            .into_iter()
            .flatten()
        {
            if let Some(value) = state
                .get("state_id")
                .and_then(JsonValue::as_str)
                .and_then(|id| updates.get(id))
            {
                state["value"] = value.clone();
            }
        }
    }
    logical
}

fn validate(arguments: &[Value]) -> Result<Value> {
    let transaction = transaction(argument(arguments, 0)?)?;
    let transaction = transaction.borrow();
    let candidate = candidate(&transaction);
    let diagnostic = NativeReasonUnitObject::from_logical(candidate).err();
    Ok(Value::Json(Rc::new(json!({
        "valid": diagnostic.is_none(),
        "diagnostics": diagnostic.map(|error| vec![json!({"code": error.code, "message": error.message})]).unwrap_or_default(),
        "operation_count": transaction.operations.len(),
    }))))
}

fn commit(arguments: &[Value]) -> Result<Value> {
    let transaction = transaction(argument(arguments, 0)?)?;
    let mut transaction = transaction.borrow_mut();
    let source_revision = transaction.snapshot.object.revision_id.as_str().to_string();
    let mut logical = transaction.snapshot.owner.object.borrow().logical.clone();
    if logical.get("current_revision").and_then(JsonValue::as_str) != Some(&source_revision) {
        transaction.closed = true;
        return Ok(Value::Json(Rc::new(json!({
            "committed": false, "diagnostic": "RUO-U1-016", "partial_commit_count": 0,
            "canonical_state_digest": canonical_digest(&logical),
        }))));
    }
    let mut updates = serde_json::Map::new();
    let mut transaction_id = format!(
        "ruo:transaction:runtime-{}",
        logical
            .get("revisions")
            .and_then(JsonValue::as_array)
            .map_or(1, |items| items.len() + 1)
    );
    for operation in &transaction.operations {
        if let Some(values) = operation
            .get("state_updates")
            .and_then(JsonValue::as_object)
        {
            updates.extend(values.clone());
        }
        if let Some(value) = operation.get("transaction_id").and_then(JsonValue::as_str) {
            transaction_id = value.to_string();
        }
    }
    let known: HashSet<String> = logical
        .get("states")
        .and_then(JsonValue::as_array)
        .into_iter()
        .flatten()
        .filter_map(|state| {
            state
                .get("state_id")
                .and_then(JsonValue::as_str)
                .map(ToOwned::to_owned)
        })
        .collect();
    if updates.keys().any(|id| !known.contains(id)) {
        transaction.closed = true;
        return Ok(Value::Json(Rc::new(json!({
            "committed": false, "diagnostic": "RUO-U1-017", "partial_commit_count": 0,
            "canonical_state_digest": canonical_digest(&logical),
        }))));
    }
    let ordinal = source_revision
        .rsplit(':')
        .next()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(0)
        + 1;
    let new_revision = format!("ruo:revision:{ordinal}");
    for state in logical
        .get_mut("states")
        .and_then(JsonValue::as_array_mut)
        .into_iter()
        .flatten()
    {
        if let Some((_, value)) = state
            .get("state_id")
            .and_then(JsonValue::as_str)
            .and_then(|id| updates.get_key_value(id))
        {
            state["value"] = value.clone();
            state["last_modified_revision"] = JsonValue::String(new_revision.clone());
        }
    }
    logical["current_revision"] = JsonValue::String(new_revision.clone());
    logical.as_object_mut().unwrap().entry("revisions").or_insert_with(|| JsonValue::Array(Vec::new()))
        .as_array_mut().unwrap().push(json!({
            "revision_id": new_revision, "transaction_id": transaction_id,
            "source_revision": source_revision, "changed_entities": updates.keys().collect::<Vec<_>>(),
        }));
    let object = match NativeReasonUnitObject::from_logical(logical.clone()) {
        Ok(object) => object,
        Err(failure) => {
            transaction.closed = true;
            return Ok(Value::Json(Rc::new(json!({
                "committed": false, "diagnostic": failure.code, "partial_commit_count": 0,
                "canonical_state_digest": canonical_digest(&transaction.snapshot.owner.object.borrow().logical),
            }))));
        }
    };
    *transaction.snapshot.owner.object.borrow_mut() = object;
    transaction.closed = true;
    Ok(Value::Json(Rc::new(json!({
        "committed": true,
        "revision_id": new_revision,
        "partial_commit_count": 0,
        "invalidation_closure": dependency_closure(&logical, updates.keys().map(String::as_str), true),
    }))))
}

fn rollback(arguments: &[Value]) -> Result<Value> {
    let transaction = transaction(argument(arguments, 0)?)?;
    transaction.borrow_mut().closed = true;
    Ok(Value::Json(Rc::new(json!({
        "committed": false, "rolled_back": true, "partial_commit_count": 0,
    }))))
}

fn select(arguments: &[Value], materialized: bool) -> Result<Value> {
    let snapshot = snapshot(argument(arguments, 0)?)?;
    let selector = json_object(argument(arguments, 1)?, "ReasonSelector")?;
    let all = entity_ids(&snapshot.object.logical);
    let selected: BTreeSet<String> = selector
        .get("entity_ids")
        .and_then(JsonValue::as_array)
        .into_iter()
        .flatten()
        .filter_map(JsonValue::as_str)
        .map(ToOwned::to_owned)
        .collect();
    let result = if selected.is_empty() {
        all
    } else {
        selected.intersection(&all).cloned().collect()
    };
    Ok(Value::Json(Rc::new(json!({
        "entity_ids": result, "materialized": materialized,
    }))))
}

fn project(arguments: &[Value]) -> Result<Value> {
    let snapshot = snapshot(argument(arguments, 0)?)?;
    let logical = &snapshot.object.logical;
    let selected = eligible_units(logical);
    let payloads: Vec<String> = logical
        .get("payloads")
        .and_then(JsonValue::as_array)
        .into_iter()
        .flatten()
        .filter(|payload| {
            payload
                .get("owner_id")
                .and_then(JsonValue::as_str)
                .is_some_and(|owner| {
                    selected.iter().any(|id| id == owner)
                        || owner == snapshot.object.object_id.as_str()
                })
        })
        .filter_map(|payload| {
            payload
                .get("payload_id")
                .and_then(JsonValue::as_str)
                .map(ToOwned::to_owned)
        })
        .collect();
    let projection_key = json!([
        snapshot.object.object_id.as_str(),
        snapshot.object.revision_id.as_str(),
        selected
    ]);
    let projection_id = format!(
        "ruo:projection:{}",
        &hex_digest(&serde_json::to_vec(&projection_key).unwrap())[..24]
    );
    Ok(Value::Json(Rc::new(json!({
        "projection_id": projection_id,
        "source_object_id": snapshot.object.object_id.as_str(),
        "source_revision": snapshot.object.revision_id.as_str(),
        "profile": "ruo.execution/1",
        "selected_units": selected,
        "selected_payloads": payloads,
        "excluded_entities": [],
        "state_snapshot_digest": canonical_digest(logical.get("states").unwrap_or(&JsonValue::Array(Vec::new()))),
        "dependency_closure": dependency_closure(logical, selected.iter().map(String::as_str), false),
        "relation_subset": [],
        "tensor_index_table": selected.iter().enumerate().map(|(index, id)| json!({"index": index, "entity_id": id})).collect::<Vec<_>>(),
        "ordering": "stable_identity", "mutates_object": false,
    }))))
}

fn save(arguments: &[Value]) -> Result<Value> {
    let snapshot = snapshot(argument(arguments, 0)?)?;
    if !snapshot.owner.filesystem_write {
        return Err(RuntimeError::new(
            "RUO-N2-007",
            "filesystem_write capability is required",
        ));
    }
    let raw = string(argument(arguments, 1)?, "ruo.save path must be a String")?;
    let policy = string(argument(arguments, 2)?, "ruo.save policy must be a String")?;
    let relative = std::path::Path::new(&raw);
    if relative.is_absolute()
        || relative.components().any(|part| {
            matches!(
                part,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        })
    {
        return Err(RuntimeError::new(
            "RUO-N2-006",
            "save path escapes resource root",
        ));
    }
    let target = confined_join(&snapshot.owner.resource_root, relative)?;
    let receipt = reasonscript_native_reasonunit_runtime::write_logical_ruo(
        &snapshot.object.logical,
        &target,
        matches!(policy.as_str(), "overwrite" | "allow" | "replace"),
    )
    .map_err(|failure| RuntimeError::new(&failure.code, failure.message))?;
    Ok(Value::Json(Rc::new(json!({
        "committed": true, "path": receipt.path, "sha256": receipt.sha256,
    }))))
}

fn confined_join(root: &std::path::Path, relative: &std::path::Path) -> Result<std::path::PathBuf> {
    let canonical_root = std::fs::canonicalize(root)
        .map_err(|error| RuntimeError::new("RUO-N2-006", error.to_string()))?;
    let candidate = canonical_root.join(relative);
    let mut existing = candidate.as_path();
    while !existing.exists() {
        existing = existing
            .parent()
            .ok_or_else(|| RuntimeError::new("RUO-N2-006", "save path escapes resource root"))?;
    }
    let canonical_existing = std::fs::canonicalize(existing)
        .map_err(|error| RuntimeError::new("RUO-N2-006", error.to_string()))?;
    if !canonical_existing.starts_with(&canonical_root) {
        return Err(RuntimeError::new(
            "RUO-N2-006",
            "save path escapes resource root",
        ));
    }
    let remainder = candidate
        .strip_prefix(existing)
        .unwrap_or(std::path::Path::new(""));
    Ok(if remainder.as_os_str().is_empty() {
        canonical_existing
    } else {
        canonical_existing.join(remainder)
    })
}

fn tensor_view(arguments: &[Value]) -> Result<Value> {
    let snapshot = snapshot(argument(arguments, 0)?)?;
    let stable_id = string(argument(arguments, 1)?, "ruo.tensor_view requires StableId")?;
    let payload = resolve_logical(&snapshot.object.logical, &stable_id)
        .ok_or_else(|| RuntimeError::new("RUO-N2-014", "Tensor payload not found"))?;
    if !payload
        .get("profile_id")
        .and_then(JsonValue::as_str)
        .is_some_and(|profile| profile.starts_with("ruo.payload.tensor"))
    {
        return Err(RuntimeError::new("RUO-N2-014", "Tensor payload not found"));
    }
    Ok(Value::Json(Rc::new(
        payload
            .get("value")
            .or_else(|| payload.get("value_ref"))
            .cloned()
            .unwrap_or(payload),
    )))
}

fn status(value: Option<&Value>) -> Result<Value> {
    let status = match value {
        Some(Value::ReasonObject(_)) => "loaded",
        Some(Value::ReasonObjectSnapshot(_)) => "snapshot",
        Some(Value::ReasonTransaction(value)) => {
            if value.borrow().closed {
                "closed"
            } else {
                "open"
            }
        }
        Some(Value::Null) | None => "absent",
        _ => "value",
    };
    Ok(Value::String(Rc::from(status)))
}

fn string(value: &Value, message: &str) -> Result<String> {
    match value {
        Value::String(value) => Ok(value.to_string()),
        _ => Err(error(message)),
    }
}

fn entity_ids(logical: &JsonValue) -> BTreeSet<String> {
    let mut result = BTreeSet::new();
    if let Some(id) = logical
        .pointer("/object_identity/entity_id")
        .and_then(JsonValue::as_str)
    {
        result.insert(id.to_string());
    }
    for registry in [
        "units",
        "payloads",
        "states",
        "relations",
        "constraints",
        "evidence_registry",
        "projection_descriptors",
        "revisions",
    ] {
        for item in logical
            .get(registry)
            .and_then(JsonValue::as_array)
            .into_iter()
            .flatten()
        {
            if let Some(id) = id_keys()
                .iter()
                .find_map(|key| item.get(key).and_then(JsonValue::as_str))
            {
                result.insert(id.to_string());
            }
        }
    }
    result
}

fn id_keys() -> [&'static str; 8] {
    [
        "entity_id",
        "payload_id",
        "state_id",
        "relation_id",
        "constraint_id",
        "evidence_id",
        "projection_id",
        "revision_id",
    ]
}

fn eligible_units(logical: &JsonValue) -> Vec<String> {
    let mut values: Vec<_> = logical
        .get("units")
        .and_then(JsonValue::as_array)
        .into_iter()
        .flatten()
        .filter(|item| {
            matches!(
                item.get("lifecycle_state").and_then(JsonValue::as_str),
                Some("active" | "reactivated")
            )
        })
        .filter_map(|item| {
            item.get("entity_id")
                .and_then(JsonValue::as_str)
                .map(ToOwned::to_owned)
        })
        .collect();
    values.sort();
    values
}

fn sorted_registry(
    logical: &JsonValue,
    registry: &str,
    key: &str,
    predicate: impl Fn(&JsonValue) -> bool,
) -> JsonValue {
    let mut values: Vec<_> = logical
        .get(registry)
        .and_then(JsonValue::as_array)
        .into_iter()
        .flatten()
        .filter(|item| predicate(item))
        .cloned()
        .collect();
    values.sort_by(|left, right| {
        left.get(key)
            .and_then(JsonValue::as_str)
            .cmp(&right.get(key).and_then(JsonValue::as_str))
    });
    JsonValue::Array(values)
}

fn knowledge_status(logical: &JsonValue, argument: Option<&str>) -> JsonValue {
    let Some(id) = argument else {
        return JsonValue::String("absent".to_string());
    };
    if let Some(value) = logical
        .pointer("/partial_loading/entity_status")
        .and_then(JsonValue::as_object)
        .and_then(|values| values.get(id))
    {
        return value.clone();
    }
    JsonValue::String(
        if entity_ids(logical).contains(id) {
            "loaded"
        } else {
            "absent"
        }
        .to_string(),
    )
}

fn dependency_closure<'a>(
    logical: &JsonValue,
    changed: impl Iterator<Item = &'a str>,
    reverse: bool,
) -> Vec<String> {
    let mut closure: BTreeSet<String> = changed.map(ToOwned::to_owned).collect();
    loop {
        let before = closure.len();
        for edge in logical
            .get("dependency_graph")
            .and_then(JsonValue::as_array)
            .into_iter()
            .flatten()
        {
            let source = edge
                .get("source_id")
                .and_then(JsonValue::as_str)
                .unwrap_or("");
            let target = edge
                .get("target_id")
                .and_then(JsonValue::as_str)
                .unwrap_or("");
            let (key, child) = if reverse {
                (target, source)
            } else {
                (source, target)
            };
            if closure.contains(key) {
                closure.insert(child.to_string());
            }
        }
        if closure.len() == before {
            break;
        }
    }
    closure.into_iter().collect()
}

fn canonical_digest(value: &JsonValue) -> String {
    reasonscript_native_reasonunit_runtime::canonical_logical_digest(value)
        .unwrap_or_else(|_| format!("sha256:{}", hex_digest(&serde_json::to_vec(value).unwrap())))
}

fn hex_digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn error(message: impl Into<String>) -> RuntimeError {
    RuntimeError::new("RUO-N2-009", message)
}
