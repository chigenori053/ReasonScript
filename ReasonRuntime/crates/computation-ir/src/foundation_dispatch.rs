//! General-purpose numeric and data foundation namespaces:
//!
//! - `math.*` — scalar math independent of Tensor handles.
//! - `sequence.range` — bounded, index-based numeric sequences.
//! - `serialize.json` — canonical in-language JSON serialization.
//! - `artifact.write_text` — permission-aware, atomic UTF-8 file output.
//!
//! Every function receives already-evaluated arguments; only
//! `artifact.write_text` touches the filesystem and it does so strictly
//! inside the runtime resource root with the `filesystem_write`
//! capability.

use std::cell::RefCell;
use std::collections::HashMap;
use std::io::Write;
use std::path::{Component, Path, PathBuf};
use std::rc::Rc;
use std::sync::atomic::{AtomicU64, Ordering};

use crate::numeric::{self, as_f64, canonical_float, finite};
use crate::value::{StructValue, Value};
use crate::vm::RuntimeError;

/// Default upper bound for `sequence.range` element counts.
pub const DEFAULT_MAX_SEQUENCE_ELEMENTS: usize = 1_000_000;
/// Default upper bound for one `artifact.write_text` payload (64 MiB).
pub const DEFAULT_MAX_ARTIFACT_TEXT_BYTES: usize = 64 * 1024 * 1024;
/// Maximum nesting depth accepted by `serialize.json`.
pub const MAX_SERIALIZE_DEPTH: usize = 256;

/// Runtime context needed by the foundation namespaces.
pub struct FoundationContext<'a> {
    pub resource_root: &'a Path,
    pub filesystem_write: bool,
    pub max_sequence_elements: usize,
    pub max_artifact_bytes: usize,
}

type VResult = Result<Value, RuntimeError>;

/// Namespaced names handled by [`call`], with their accepted arities.
pub fn arity(function_id: &str) -> Option<(usize, usize)> {
    Some(match function_id {
        "math.abs" | "math.floor" | "math.ceil" | "math.round" | "math.sqrt" | "math.sin"
        | "math.cos" | "math.tan" | "math.log" | "math.exp" => (1, 1),
        "math.min" | "math.max" => (2, 2),
        "math.approx_equal" => (3, 3),
        "sequence.range" => (3, 3),
        "serialize.json" => (1, 1),
        "artifact.write_text" => (2, 3),
        _ => return None,
    })
}

fn family(function_id: &str) -> &'static str {
    match function_id.split('.').next().unwrap_or_default() {
        "math" => "MATH",
        "sequence" => "SEQ",
        "serialize" => "SER",
        _ => "ART",
    }
}

pub fn call(function_id: &str, args: Vec<Value>, context: &FoundationContext<'_>) -> VResult {
    let family = family(function_id);
    let Some((minimum, maximum)) = arity(function_id) else {
        return Err(RuntimeError::new(
            format!("{family}-001").as_str(),
            format!("unknown foundation function: {function_id}"),
        ));
    };
    if args.len() < minimum || args.len() > maximum {
        let expected = if minimum == maximum {
            minimum.to_string()
        } else {
            format!("{minimum} to {maximum}")
        };
        return Err(RuntimeError::new(
            format!("{family}-002").as_str(),
            format!(
                "{function_id} expects {expected} arguments, got {}",
                args.len()
            ),
        ));
    }
    match function_id.split_once('.').map(|(namespace, _)| namespace) {
        Some("math") => call_math(function_id, &args),
        Some("sequence") => sequence_range(&args, context.max_sequence_elements),
        Some("serialize") => serialize_json(&args[0]).map(|text| Value::String(Rc::from(text))),
        _ => write_text(&args, context),
    }
}

// ---------------------------------------------------------------- math.*

fn math_number(function_id: &str, value: &Value, position: &str) -> Result<f64, RuntimeError> {
    as_f64(value).ok_or_else(|| {
        RuntimeError::new(
            "MATH-003",
            format!(
                "{function_id} {position} argument must be Int or Float, got {}",
                value.type_name()
            ),
        )
    })
}

fn domain(function_id: &str, message: &str) -> RuntimeError {
    RuntimeError::new("MATH-004", format!("{function_id} domain error: {message}"))
}

fn call_math(function_id: &str, args: &[Value]) -> VResult {
    let name = &function_id["math.".len()..];
    match name {
        "abs" => match &args[0] {
            Value::Int(value) => value.checked_abs().map(Value::Int).ok_or_else(|| {
                RuntimeError::new(numeric::OVERFLOW, "math.abs overflows the 64-bit Int range")
            }),
            other => Ok(Value::Float(
                math_number(function_id, other, "first")?.abs(),
            )),
        },
        "min" | "max" => {
            if let (Value::Int(a), Value::Int(b)) = (&args[0], &args[1]) {
                return Ok(Value::Int(if name == "min" {
                    *a.min(b)
                } else {
                    *a.max(b)
                }));
            }
            let a = math_number(function_id, &args[0], "first")?;
            let b = math_number(function_id, &args[1], "second")?;
            // Ties return the first argument, so min(0.0, -0.0) is 0.0.
            let value = match name {
                "min" if b < a => b,
                "max" if b > a => b,
                _ => a,
            };
            Ok(Value::Float(value))
        }
        "floor" | "ceil" | "round" => match &args[0] {
            Value::Int(value) => Ok(Value::Int(*value)),
            other => {
                let value = math_number(function_id, other, "first")?;
                Ok(Value::Float(match name {
                    "floor" => value.floor(),
                    "ceil" => value.ceil(),
                    // Half-way cases round away from zero.
                    _ => value.round(),
                }))
            }
        },
        "sqrt" => {
            let value = math_number(function_id, &args[0], "first")?;
            if value < 0.0 {
                return Err(domain(function_id, "argument must be >= 0"));
            }
            Ok(Value::Float(value.sqrt()))
        }
        "log" => {
            let value = math_number(function_id, &args[0], "first")?;
            if value <= 0.0 {
                return Err(domain(function_id, "argument must be > 0"));
            }
            Ok(Value::Float(value.ln()))
        }
        "exp" => {
            let value = math_number(function_id, &args[0], "first")?;
            finite(function_id, value.exp()).map(Value::Float)
        }
        "sin" | "cos" | "tan" => {
            let value = math_number(function_id, &args[0], "first")?;
            let result = match name {
                "sin" => value.sin(),
                "cos" => value.cos(),
                _ => value.tan(),
            };
            finite(function_id, result).map(Value::Float)
        }
        "approx_equal" => {
            let a = math_number(function_id, &args[0], "first")?;
            let b = math_number(function_id, &args[1], "second")?;
            let tolerance = math_number(function_id, &args[2], "third")?;
            if tolerance < 0.0 {
                return Err(domain(function_id, "tolerance must be >= 0"));
            }
            // |a - b| may exceed the Float range for finite inputs; such a
            // difference is never within a finite tolerance.
            Ok(Value::Bool((a - b).abs() <= tolerance))
        }
        _ => Err(RuntimeError::new(
            "MATH-001",
            format!("unknown foundation function: {function_id}"),
        )),
    }
}

// ---------------------------------------------------------- sequence.*

fn sequence_limit_error(limit: usize) -> RuntimeError {
    RuntimeError::new(
        "SEQ-005",
        format!("sequence.range exceeds max_sequence_elements ({limit})"),
    )
}

fn sequence_range(args: &[Value], limit: usize) -> VResult {
    for (value, position) in args.iter().zip(["start", "end", "step"]) {
        if as_f64(value).is_none() {
            return Err(RuntimeError::new(
                "SEQ-003",
                format!(
                    "sequence.range {position} must be Int or Float, got {}",
                    value.type_name()
                ),
            ));
        }
    }
    if let (Value::Int(start), Value::Int(end), Value::Int(step)) = (&args[0], &args[1], &args[2]) {
        return int_range(*start, *end, *step, limit);
    }
    let start = as_f64(&args[0]).unwrap_or_default();
    let end = as_f64(&args[1]).unwrap_or_default();
    let step = as_f64(&args[2]).unwrap_or_default();
    float_range(start, end, step, limit)
}

fn zero_step() -> RuntimeError {
    RuntimeError::new("SEQ-004", "sequence.range step must not be zero")
}

fn int_range(start: i64, end: i64, step: i64, limit: usize) -> VResult {
    if step == 0 {
        return Err(zero_step());
    }
    let (start, end, step) = (start as i128, end as i128, step as i128);
    let span = if step > 0 { end - start } else { start - end };
    let count = if span <= 0 {
        0
    } else {
        let magnitude = step.abs();
        (span + magnitude - 1) / magnitude
    };
    if count > limit as i128 {
        return Err(sequence_limit_error(limit));
    }
    let items = (0..count)
        .map(|index| Value::Int((start + step * index) as i64))
        .collect();
    Ok(Value::Array(Rc::new(RefCell::new(items))))
}

fn float_range(start: f64, end: f64, step: f64, limit: usize) -> VResult {
    if step == 0.0 {
        return Err(zero_step());
    }
    // Elements are exactly value(i) = start + step * i for every i >= 0
    // with value(i) strictly before `end` in the step direction.
    let value = |index: f64| start + step * index;
    let before_end = |candidate: f64| {
        if step > 0.0 {
            candidate < end
        } else {
            candidate > end
        }
    };
    if !before_end(start) {
        return Ok(Value::Array(Rc::new(RefCell::new(Vec::new()))));
    }
    // The quotient may underflow to zero for a huge step; at least `start`
    // itself is an element here.
    let estimate = ((end - start) / step).ceil().max(1.0);
    // Reject oversized requests before allocating; the +1 absorbs the
    // one-element rounding correction below.
    if !estimate.is_finite() || estimate > limit as f64 + 1.0 {
        return Err(sequence_limit_error(limit));
    }
    let mut count = estimate as usize;
    while count > 0 && !before_end(value((count - 1) as f64)) {
        count -= 1;
    }
    while before_end(value(count as f64)) {
        count += 1;
        if count > limit {
            return Err(sequence_limit_error(limit));
        }
    }
    if count > limit {
        return Err(sequence_limit_error(limit));
    }
    let mut items = Vec::with_capacity(count);
    for index in 0..count {
        items.push(Value::Float(finite("sequence.range", value(index as f64))?));
    }
    Ok(Value::Array(Rc::new(RefCell::new(items))))
}

// --------------------------------------------------------- serialize.*

/// Canonical JSON text for a ReasonScript value (no insignificant
/// whitespace, struct fields and object keys in ascending code-point
/// order, canonical float text, UTF-8 output).
pub fn serialize_json(value: &Value) -> Result<String, RuntimeError> {
    let mut output = String::new();
    write_value(value, &mut output, 0)?;
    Ok(output)
}

fn depth_error() -> RuntimeError {
    RuntimeError::new(
        "SER-004",
        format!(
            "serialize.json nesting exceeds {MAX_SERIALIZE_DEPTH} levels (or the value is cyclic)"
        ),
    )
}

fn write_value(value: &Value, output: &mut String, depth: usize) -> Result<(), RuntimeError> {
    if depth > MAX_SERIALIZE_DEPTH {
        return Err(depth_error());
    }
    match value {
        Value::Null | Value::Optional(None) => output.push_str("null"),
        Value::Bool(value) => output.push_str(if *value { "true" } else { "false" }),
        Value::Int(value) => output.push_str(&value.to_string()),
        Value::Float(value) => {
            finite("serialize.json", *value)?;
            output.push_str(&canonical_float(*value));
        }
        Value::String(value) => write_string(value, output),
        Value::Enum {
            enum_name,
            variant_name,
        } => write_string(&format!("{enum_name}.{variant_name}"), output),
        Value::Optional(Some(inner)) => write_value(inner, output, depth + 1)?,
        Value::Array(items) => {
            let items = items.try_borrow().map_err(|_| depth_error())?;
            output.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                write_value(item, output, depth + 1)?;
            }
            output.push(']');
        }
        Value::Struct(value) => {
            let fields = value.fields.try_borrow().map_err(|_| depth_error())?;
            let mut names: Vec<&String> = fields.keys().collect();
            names.sort();
            output.push('{');
            for (index, name) in names.into_iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                write_string(name, output);
                output.push(':');
                write_value(&fields[name], output, depth + 1)?;
            }
            output.push('}');
        }
        Value::Json(value) => write_json(value, output, depth)?,
        other => {
            return Err(RuntimeError::new(
                "SER-003",
                format!(
                    "serialize.json does not support {} values",
                    other.type_name()
                ),
            ))
        }
    }
    Ok(())
}

fn write_json(
    value: &serde_json::Value,
    output: &mut String,
    depth: usize,
) -> Result<(), RuntimeError> {
    if depth > MAX_SERIALIZE_DEPTH {
        return Err(depth_error());
    }
    match value {
        serde_json::Value::Null => output.push_str("null"),
        serde_json::Value::Bool(value) => output.push_str(if *value { "true" } else { "false" }),
        serde_json::Value::Number(number) => match number.as_i64() {
            Some(value) => output.push_str(&value.to_string()),
            None if number.as_u64().is_some() => {
                output.push_str(&number.as_u64().unwrap().to_string());
            }
            None => {
                let value = number.as_f64().unwrap_or(f64::NAN);
                finite("serialize.json", value)?;
                output.push_str(&canonical_float(value));
            }
        },
        serde_json::Value::String(value) => write_string(value, output),
        serde_json::Value::Array(items) => {
            output.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                write_json(item, output, depth + 1)?;
            }
            output.push(']');
        }
        serde_json::Value::Object(map) => {
            let mut names: Vec<&String> = map.keys().collect();
            names.sort();
            output.push('{');
            for (index, name) in names.into_iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                write_string(name, output);
                output.push(':');
                write_json(&map[name], output, depth + 1)?;
            }
            output.push('}');
        }
    }
    Ok(())
}

/// JSON string escaping: `"` `\` and the short escapes `\b \f \n \r \t`;
/// other control characters as lowercase `\u00xx`; everything else,
/// including non-ASCII text, is emitted verbatim as UTF-8.
fn write_string(value: &str, output: &mut String) {
    output.push('"');
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            '\u{08}' => output.push_str("\\b"),
            '\u{0c}' => output.push_str("\\f"),
            control if (control as u32) < 0x20 => {
                output.push_str(&format!("\\u{:04x}", control as u32));
            }
            other => output.push(other),
        }
    }
    output.push('"');
}

// ----------------------------------------------------------- artifact.*

static TEMPORARY_COUNTER: AtomicU64 = AtomicU64::new(0);

fn artifact_error(code: &str, message: impl Into<String>) -> RuntimeError {
    RuntimeError::new(code, message)
}

/// Validates an artifact path and returns its normalized relative
/// components. Paths are relative to the resource root; absolute paths,
/// `.`/`..` components, backslashes, and empty segments are rejected.
fn artifact_components(raw: &str) -> Result<Vec<String>, RuntimeError> {
    let invalid = |reason: &str| {
        artifact_error(
            "ART-005",
            format!("invalid artifact path {raw:?}: {reason}"),
        )
    };
    if raw.is_empty() {
        return Err(invalid("path is empty"));
    }
    if raw.contains('\\') || raw.contains('\0') {
        return Err(invalid("backslashes and NUL characters are not allowed"));
    }
    if raw.starts_with('/') || Path::new(raw).is_absolute() {
        return Err(invalid("absolute paths are not allowed"));
    }
    let mut components = Vec::new();
    for segment in raw.split('/') {
        if segment.is_empty() {
            return Err(invalid("empty path segments are not allowed"));
        }
        match Path::new(segment).components().next() {
            Some(Component::Normal(_)) if segment != "." && segment != ".." => {
                components.push(segment.to_owned());
            }
            _ => return Err(invalid("'.' and '..' segments are not allowed")),
        }
    }
    Ok(components)
}

fn write_text(args: &[Value], context: &FoundationContext<'_>) -> VResult {
    let path = match &args[0] {
        Value::String(value) => value.to_string(),
        other => {
            return Err(artifact_error(
                "ART-003",
                format!(
                    "artifact.write_text path must be String, got {}",
                    other.type_name()
                ),
            ))
        }
    };
    let content = match &args[1] {
        Value::String(value) => Rc::clone(value),
        other => {
            return Err(artifact_error(
                "ART-003",
                format!(
                    "artifact.write_text content must be String, got {}",
                    other.type_name()
                ),
            ))
        }
    };
    let overwrite = match args.get(2) {
        None => false,
        Some(Value::Bool(value)) => *value,
        Some(other) => {
            return Err(artifact_error(
                "ART-003",
                format!(
                    "artifact.write_text overwrite must be Bool, got {}",
                    other.type_name()
                ),
            ))
        }
    };
    if !context.filesystem_write {
        return Err(artifact_error(
            "ART-004",
            "artifact.write_text requires the filesystem_write capability (--allow-write)",
        ));
    }
    let components = artifact_components(&path)?;
    let bytes = content.as_bytes();
    if bytes.len() > context.max_artifact_bytes {
        return Err(artifact_error(
            "ART-008",
            format!(
                "artifact content is {} bytes; the limit is {}",
                bytes.len(),
                context.max_artifact_bytes
            ),
        ));
    }
    let io_error = |error: std::io::Error| {
        artifact_error("ART-009", format!("artifact write failed: {error}"))
    };
    let root = context.resource_root.canonicalize().map_err(io_error)?;
    let (file_name, parents) = components.split_last().expect("non-empty components");
    let mut parent = root.clone();
    parent.extend(parents);
    if !parent.is_dir() {
        return Err(artifact_error(
            "ART-007",
            format!("artifact directory does not exist: {}", parents.join("/")),
        ));
    }
    // Resolve symbolic links so a linked directory cannot escape the root.
    let parent = parent.canonicalize().map_err(io_error)?;
    if !parent.starts_with(&root) {
        return Err(artifact_error(
            "ART-005",
            format!("invalid artifact path {path:?}: resolves outside the artifact root"),
        ));
    }
    let target = parent.join(file_name);
    match std::fs::symlink_metadata(&target) {
        Ok(metadata) if metadata.is_dir() => {
            return Err(artifact_error(
                "ART-006",
                format!("artifact target is a directory: {path}"),
            ))
        }
        Ok(_) if !overwrite => {
            return Err(artifact_error(
                "ART-006",
                format!("artifact already exists: {path} (pass overwrite = true to replace it)"),
            ))
        }
        _ => {}
    }
    let temporary = temporary_path(&parent, file_name);
    let published = write_temporary(&temporary, bytes).and_then(|()| {
        if overwrite {
            std::fs::rename(&temporary, &target)
        } else {
            // A hard link publishes without replacing a file created
            // concurrently; it fails with AlreadyExists in that case.
            std::fs::hard_link(&temporary, &target).and_then(|()| std::fs::remove_file(&temporary))
        }
    });
    if let Err(error) = published {
        let _ = std::fs::remove_file(&temporary);
        if error.kind() == std::io::ErrorKind::AlreadyExists {
            return Err(artifact_error(
                "ART-006",
                format!("artifact already exists: {path} (pass overwrite = true to replace it)"),
            ));
        }
        return Err(io_error(error));
    }
    let mut fields = HashMap::new();
    fields.insert(
        "path".to_owned(),
        Value::String(Rc::from(components.join("/"))),
    );
    fields.insert("bytes_written".to_owned(), Value::Int(bytes.len() as i64));
    Ok(Value::Struct(Rc::new(StructValue {
        type_name: "ArtifactResult".to_owned(),
        fields: RefCell::new(fields),
    })))
}

fn temporary_path(parent: &Path, file_name: &str) -> PathBuf {
    let counter = TEMPORARY_COUNTER.fetch_add(1, Ordering::Relaxed);
    parent.join(format!(".{file_name}.{}.{counter}.tmp", std::process::id()))
}

fn write_temporary(path: &Path, bytes: &[u8]) -> std::io::Result<()> {
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    file.write_all(bytes)?;
    file.sync_all()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn context(root: &Path) -> FoundationContext<'_> {
        FoundationContext {
            resource_root: root,
            filesystem_write: true,
            max_sequence_elements: 100,
            max_artifact_bytes: 1024,
        }
    }

    fn floats(value: Value) -> Vec<f64> {
        match value {
            Value::Array(items) => items
                .borrow()
                .iter()
                .map(|item| as_f64(item).unwrap())
                .collect(),
            other => panic!("expected array, got {other:?}"),
        }
    }

    fn run(function_id: &str, args: Vec<Value>) -> VResult {
        call(function_id, args, &context(Path::new(".")))
    }

    #[test]
    fn integer_ranges_follow_start_inclusive_end_exclusive() {
        assert_eq!(
            floats(
                run(
                    "sequence.range",
                    vec![Value::Int(0), Value::Int(5), Value::Int(1)]
                )
                .unwrap()
            ),
            vec![0.0, 1.0, 2.0, 3.0, 4.0]
        );
        assert_eq!(
            floats(
                run(
                    "sequence.range",
                    vec![Value::Int(5), Value::Int(0), Value::Int(-1)]
                )
                .unwrap()
            ),
            vec![5.0, 4.0, 3.0, 2.0, 1.0]
        );
        assert!(floats(
            run(
                "sequence.range",
                vec![Value::Int(0), Value::Int(5), Value::Int(-1)]
            )
            .unwrap()
        )
        .is_empty());
        assert!(floats(
            run(
                "sequence.range",
                vec![Value::Int(0), Value::Int(0), Value::Int(1)]
            )
            .unwrap()
        )
        .is_empty());
        assert_eq!(
            run(
                "sequence.range",
                vec![Value::Int(0), Value::Int(5), Value::Int(0)]
            )
            .unwrap_err()
            .code,
            "SEQ-004"
        );
        assert_eq!(
            run(
                "sequence.range",
                vec![Value::Int(0), Value::Int(101), Value::Int(1)]
            )
            .unwrap_err()
            .code,
            "SEQ-005"
        );
        assert_eq!(
            run(
                "sequence.range",
                vec![Value::Int(i64::MIN), Value::Int(i64::MAX), Value::Int(1)]
            )
            .unwrap_err()
            .code,
            "SEQ-005"
        );
    }

    #[test]
    fn float_ranges_are_index_based() {
        let values = floats(
            run(
                "sequence.range",
                vec![Value::Float(0.0), Value::Float(1.0), Value::Float(0.1)],
            )
            .unwrap(),
        );
        assert_eq!(values.len(), 10);
        for (index, value) in values.iter().enumerate() {
            assert_eq!(*value, 0.1 * index as f64);
        }
        let values = floats(
            run(
                "sequence.range",
                vec![Value::Float(0.0), Value::Float(0.3), Value::Float(0.1)],
            )
            .unwrap(),
        );
        assert_eq!(values, vec![0.0, 0.1, 0.2]);
        assert_eq!(
            run(
                "sequence.range",
                vec![Value::Float(0.0), Value::Float(1e300), Value::Float(1e-300)]
            )
            .unwrap_err()
            .code,
            "SEQ-005"
        );
    }

    #[test]
    fn scalar_math_domains_and_types() {
        assert!(
            matches!(run("math.sqrt", vec![Value::Int(4)]).unwrap(), Value::Float(v) if v == 2.0)
        );
        assert_eq!(
            run("math.sqrt", vec![Value::Float(-1.0)]).unwrap_err().code,
            "MATH-004"
        );
        assert_eq!(
            run("math.log", vec![Value::Int(0)]).unwrap_err().code,
            "MATH-004"
        );
        assert_eq!(
            run("math.exp", vec![Value::Float(1000.0)])
                .unwrap_err()
                .code,
            "RT-NUM-OVERFLOW"
        );
        assert!(matches!(
            run("math.abs", vec![Value::Int(-3)]).unwrap(),
            Value::Int(3)
        ));
        assert_eq!(
            run("math.abs", vec![Value::Int(i64::MIN)])
                .unwrap_err()
                .code,
            "RT-NUM-OVERFLOW"
        );
        assert!(
            matches!(run("math.round", vec![Value::Float(2.5)]).unwrap(), Value::Float(v) if v == 3.0)
        );
        assert!(
            matches!(run("math.round", vec![Value::Float(-2.5)]).unwrap(), Value::Float(v) if v == -3.0)
        );
        assert!(
            matches!(run("math.max", vec![Value::Int(1), Value::Float(1.5)]).unwrap(), Value::Float(v) if v == 1.5)
        );
        assert_eq!(
            run(
                "math.approx_equal",
                vec![Value::Float(1.0), Value::Float(1.0), Value::Float(-1.0)]
            )
            .unwrap_err()
            .code,
            "MATH-004"
        );
        assert_eq!(
            run("math.sqrt", vec![Value::Bool(true)]).unwrap_err().code,
            "MATH-003"
        );
    }

    #[test]
    fn canonical_json_is_sorted_and_escaped() {
        let mut fields = HashMap::new();
        fields.insert("z".to_owned(), Value::Float(-0.0));
        fields.insert("a".to_owned(), Value::String(Rc::from("é\"\n\u{1}")));
        fields.insert("m".to_owned(), Value::Optional(None));
        let value = Value::Struct(Rc::new(StructValue {
            type_name: "Row".to_owned(),
            fields: RefCell::new(fields),
        }));
        assert_eq!(
            serialize_json(&value).unwrap(),
            "{\"a\":\"é\\\"\\n\\u0001\",\"m\":null,\"z\":-0.0}"
        );
        assert_eq!(
            serialize_json(&Value::Tensor(Rc::from("tensor_0001")))
                .unwrap_err()
                .code,
            "SER-003"
        );
    }

    #[test]
    fn json_number_boundaries_keep_integer_precision() {
        for number in [
            i64::MIN.to_string(),
            i64::MAX.to_string(),
            (1_u64 << 53).to_string(),
            ((1_u64 << 53) + 1).to_string(),
            u64::MAX.to_string(),
        ] {
            let json: serde_json::Value = serde_json::from_str(&number).unwrap();
            assert_eq!(serialize_json(&Value::Json(Rc::new(json))).unwrap(), number);
        }
    }

    #[test]
    fn artifact_paths_are_confined() {
        for path in ["", "/etc/passwd", "../x", "a/../b", "./a", "a//b", "a\\b", "a\0b"] {
            assert_eq!(
                artifact_components(path).unwrap_err().code,
                "ART-005",
                "{path}"
            );
        }
        assert_eq!(
            artifact_components("out/data.json").unwrap(),
            vec!["out", "data.json"]
        );
    }
}
