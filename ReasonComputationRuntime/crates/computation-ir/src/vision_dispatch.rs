//! In-process dispatch for the two `vision.*` standard functions.

use std::fs;
use std::path::{Component, Path, PathBuf};
use std::rc::Rc;

use reasonscript_vision_runtime::{build_ruo, infer_from_manifest, VisionObservation, PROFILE};
use serde_json::{json, Value as JsonValue};

use crate::value::{to_json, Value};
use crate::vm::RuntimeError;

type Result<T> = std::result::Result<T, RuntimeError>;

pub fn call(
    function_id: &str,
    arguments: &[Value],
    resource_root: &Path,
    filesystem_read: bool,
    filesystem_write: bool,
) -> Result<(Value, JsonValue)> {
    match function_id {
        "vision.infer" => infer(arguments, resource_root, filesystem_read),
        "vision.build_ruo" => build(arguments, resource_root, filesystem_write),
        _ => Err(RuntimeError::new(
            "VIS-LANG-001",
            format!("unknown Vision function: {function_id}"),
        )),
    }
}

fn infer(
    arguments: &[Value],
    resource_root: &Path,
    filesystem_read: bool,
) -> Result<(Value, JsonValue)> {
    if !filesystem_read {
        return Err(RuntimeError::new(
            "VIS-CAP-001",
            "vision.infer requires filesystem_read capability",
        ));
    }
    let model_argument = string(argument(arguments, 0)?)?;
    let image_argument = string(argument(arguments, 1)?)?;
    let model = resolve(resource_root, &model_argument)?;
    let image = resolve(resource_root, &image_argument)?;
    let observation = infer_from_manifest(&model, &image)
        .map_err(|error| RuntimeError::new(&error.code, error.message))?;
    let observation_json = serde_json::to_value(&observation)
        .map_err(|error| RuntimeError::new("VIS-RUN-003", error.to_string()))?;
    let trace = json!({
        "operation": "vision_infer",
        "model": model_argument,
        "image": image_argument,
        "observation_id": observation.observation_id,
        "native_profile": PROFILE,
    });
    Ok((Value::Json(Rc::new(observation_json)), trace))
}

fn build(
    arguments: &[Value],
    resource_root: &Path,
    filesystem_write: bool,
) -> Result<(Value, JsonValue)> {
    if !filesystem_write {
        return Err(RuntimeError::new(
            "VIS-CAP-002",
            "vision.build_ruo requires filesystem_write capability",
        ));
    }
    let observation_json = to_json(argument(arguments, 0)?);
    let observation: VisionObservation =
        serde_json::from_value(observation_json).map_err(|_| {
            RuntimeError::new(
                "VIS-LANG-005",
                "vision.build_ruo requires VisionObservation",
            )
        })?;
    let output_argument = string(argument(arguments, 1)?)?;
    let output = resolve(resource_root, &output_argument)?;
    if output.extension().and_then(|value| value.to_str()) != Some("ruo") {
        return Err(RuntimeError::new(
            "VIS-LANG-004",
            "Vision Object output must use lowercase .ruo",
        ));
    }
    if output.exists() {
        return Err(RuntimeError::new(
            "VIS-PUB-001",
            "Vision Object output already exists",
        ));
    }
    let bundle =
        build_ruo(&observation).map_err(|error| RuntimeError::new(&error.code, error.message))?;
    reasonscript_native_reasonunit_runtime::NativeReasonUnitObject::from_logical(
        bundle.object.clone(),
    )
    .map_err(|_| RuntimeError::new("VIS-PUB-002", "generated Object failed RUO-U1 validation"))?;

    let parent = output.parent().unwrap_or(resource_root);
    fs::create_dir_all(parent)
        .map_err(|error| RuntimeError::new("VIS-PUB-005", error.to_string()))?;
    let mut published = Vec::new();
    let publication = (|| -> Result<()> {
        for (locator, bytes) in &bundle.resources {
            let relative = safe_locator(locator)?;
            let target = confined_join(parent, relative)?;
            if target.exists() {
                let existing = fs::read(&target)
                    .map_err(|error| RuntimeError::new("VIS-PUB-005", error.to_string()))?;
                if existing != *bytes {
                    return Err(RuntimeError::new(
                        "VIS-PUB-004",
                        format!("resource already exists with different bytes: {locator}"),
                    ));
                }
                continue;
            }
            if let Some(resource_parent) = target.parent() {
                fs::create_dir_all(resource_parent)
                    .map_err(|error| RuntimeError::new("VIS-PUB-005", error.to_string()))?;
            }
            let temporary = target.with_file_name(format!(
                ".{}.{}.tmp",
                target
                    .file_name()
                    .and_then(|value| value.to_str())
                    .unwrap_or("vision"),
                std::process::id()
            ));
            fs::write(&temporary, bytes)
                .and_then(|_| fs::rename(&temporary, &target))
                .map_err(|error| RuntimeError::new("VIS-PUB-005", error.to_string()))?;
            published.push(target);
        }
        reasonscript_native_reasonunit_runtime::write_logical_ruo(&bundle.object, &output, false)
            .map_err(|error| RuntimeError::new("VIS-PUB-002", error.message))?;
        Ok(())
    })();
    if let Err(error) = publication {
        if !output.exists() {
            for path in published.iter().rev() {
                let _ = fs::remove_file(path);
            }
        }
        return Err(error);
    }

    let object_id = bundle
        .object
        .pointer("/object_identity/entity_id")
        .and_then(JsonValue::as_str)
        .unwrap_or("")
        .to_owned();
    let result = json!({
        "status": "committed",
        "object_id": object_id,
        "path": output_argument,
        "profile": "reasonscript-vision-build-result/0.1",
    });
    let trace = json!({
        "operation": "vision_build_ruo",
        "output": output_argument,
        "object_id": object_id,
        "transaction_boundary": "atomic_ruo_f1",
    });
    Ok((Value::Json(Rc::new(result)), trace))
}

fn argument(arguments: &[Value], index: usize) -> Result<&Value> {
    arguments
        .get(index)
        .ok_or_else(|| RuntimeError::new("VIS-LANG-002", "Vision function argument count mismatch"))
}

fn string(value: &Value) -> Result<String> {
    match value {
        Value::String(value) => Ok(value.to_string()),
        _ => Err(RuntimeError::new(
            "VIS-LANG-003",
            "Vision path argument must be string",
        )),
    }
}

fn resolve(root: &Path, value: &str) -> Result<PathBuf> {
    let path = Path::new(value);
    if value.is_empty()
        || value.contains('\\')
        || path.is_absolute()
        || path.components().any(|part| {
            matches!(
                part,
                Component::CurDir
                    | Component::ParentDir
                    | Component::RootDir
                    | Component::Prefix(_)
            )
        })
    {
        return Err(RuntimeError::new("VIS-SEC-001", "unsafe Vision path"));
    }
    confined_join(root, path)
}

fn safe_locator(value: &str) -> Result<&Path> {
    let path = Path::new(value);
    if value.is_empty()
        || value.contains('\\')
        || path.is_absolute()
        || path.components().any(|part| {
            matches!(
                part,
                Component::CurDir
                    | Component::ParentDir
                    | Component::RootDir
                    | Component::Prefix(_)
            )
        })
    {
        return Err(RuntimeError::new(
            "VIS-SEC-002",
            "unsafe Tensor resource locator",
        ));
    }
    Ok(path)
}

fn confined_join(root: &Path, relative: &Path) -> Result<PathBuf> {
    let canonical_root = fs::canonicalize(root)
        .map_err(|error| RuntimeError::new("VIS-SEC-001", error.to_string()))?;
    let candidate = canonical_root.join(relative);
    let mut existing = candidate.as_path();
    while !existing.exists() {
        existing = existing
            .parent()
            .ok_or_else(|| RuntimeError::new("VIS-SEC-001", "Vision path escapes project root"))?;
    }
    let canonical_existing = fs::canonicalize(existing)
        .map_err(|error| RuntimeError::new("VIS-SEC-001", error.to_string()))?;
    if !canonical_existing.starts_with(&canonical_root) {
        return Err(RuntimeError::new(
            "VIS-SEC-001",
            "Vision path escapes project root",
        ));
    }
    let remainder = candidate.strip_prefix(existing).unwrap_or(Path::new(""));
    Ok(if remainder.as_os_str().is_empty() {
        canonical_existing
    } else {
        canonical_existing.join(remainder)
    })
}
