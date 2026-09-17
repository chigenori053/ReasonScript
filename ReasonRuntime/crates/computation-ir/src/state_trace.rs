//! Incremental state tracing. Only writes visit a collection; loop boundaries
//! retain hashes and changes, never a copy of the whole environment.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::rc::Rc;

use serde_json::{json, Value as Json};
use sha2::{Digest, Sha256};

use crate::value::{to_json, Value};
use crate::vm::RuntimeError;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TraceMode {
    Off,
    Delta,
    Full,
    Sampled,
}

#[derive(Clone, Debug)]
pub struct TraceConfig {
    pub mode: TraceMode,
    pub checkpoint_interval: u64,
    pub max_bytes: usize,
}

impl Default for TraceConfig {
    fn default() -> Self {
        Self {
            mode: TraceMode::Delta,
            checkpoint_interval: 1_000,
            max_bytes: 104_857_600,
        }
    }
}

impl TraceConfig {
    pub fn from_json(value: &Json) -> Result<Self, RuntimeError> {
        if value
            .get("enabled")
            .is_some_and(|value| !value.is_boolean())
            || value.get("mode").is_some_and(|value| !value.is_string())
        {
            return Err(RuntimeError::new(
                "TRACE-DELTA-001",
                "trace enabled/mode have invalid types",
            ));
        }
        let mode = match value.get("mode").and_then(Json::as_str) {
            Some("off") => TraceMode::Off,
            Some("delta") => TraceMode::Delta,
            Some("full") => TraceMode::Full,
            Some("sampled") => TraceMode::Sampled,
            None if value.get("enabled").and_then(Json::as_bool) == Some(false) => TraceMode::Off,
            None => TraceMode::Delta,
            _ => return Err(RuntimeError::new("TRACE-DELTA-001", "invalid trace mode")),
        };
        let mut config = Self {
            mode,
            ..Self::default()
        };
        if let Some(value) = value.get("checkpoint_interval") {
            config.checkpoint_interval = value.as_u64().ok_or_else(|| {
                RuntimeError::new(
                    "TRACE-DELTA-001",
                    "checkpoint_interval must be a nonnegative integer",
                )
            })?;
        }
        if let Some(value) = value.get("max_bytes") {
            config.max_bytes = value
                .as_u64()
                .and_then(|n| usize::try_from(n).ok())
                .ok_or_else(|| {
                    RuntimeError::new("TRACE-DELTA-001", "max_bytes must be a nonnegative integer")
                })?;
        }
        Ok(config)
    }
}

pub fn visible(name: &str) -> bool {
    !["__for_", "__trace_", "__opt_"]
        .iter()
        .any(|prefix| name.starts_with(prefix))
}

type Path = Vec<String>;
type Identity = (u8, usize);

fn identity(value: &Value) -> Option<Identity> {
    match value {
        Value::Array(value) => Some((0, Rc::as_ptr(value) as usize)),
        Value::Struct(value) => Some((1, Rc::as_ptr(value) as usize)),
        Value::ArrayBuilder(value) => Some((2, Rc::as_ptr(value) as usize)),
        Value::ReasonObject(value) => Some((3, Rc::as_ptr(value) as usize)),
        Value::ReasonTransaction(value) => Some((4, Rc::as_ptr(value) as usize)),
        _ => None,
    }
}

fn pointer(path: &[String]) -> String {
    path.iter()
        .map(|part| format!("/{}", part.replace('~', "~0").replace('/', "~1")))
        .collect()
}

struct LoopFrame {
    iteration: i64,
}

#[derive(Default)]
pub struct TraceState {
    state: BTreeMap<String, Json>,
    digest: [u8; 32],
    aliases: HashMap<Identity, BTreeSet<Path>>,
    loops: HashMap<String, Vec<LoopFrame>>,
    previous_hash: Option<String>,
    changes: Vec<Json>,
    pub previous_event_id: Option<u64>,
    pub frame_id: u64,
}

impl TraceState {
    pub fn new(env: &HashMap<String, Value>) -> Self {
        let mut result = Self::default();
        for (name, value) in env {
            result.assign(name, None, value);
        }
        result
    }

    pub fn hash(&self) -> String {
        let digest = Sha256::digest(self.digest);
        format!("sha256-xor-leaves/1:{digest:x}")
    }

    pub fn checkpoint(&self) -> Json {
        json!(self.state)
    }

    pub fn begin(&mut self, loop_id: &str, iteration: i64) {
        if self.previous_hash.is_none() {
            self.previous_hash = Some(self.hash());
        }
        self.loops
            .entry(loop_id.to_owned())
            .or_default()
            .push(LoopFrame { iteration });
    }

    pub fn end(&mut self, loop_id: &str) -> Result<Json, RuntimeError> {
        let frame = self
            .loops
            .get_mut(loop_id)
            .and_then(Vec::pop)
            .ok_or_else(|| RuntimeError::new("TRACE-DELTA-001", "loop trace frame is missing"))?;
        let mut event = self.flush();
        event["loop_id"] = json!(loop_id);
        event["iteration"] = json!(frame.iteration);
        event["condition"] = json!(true);
        Ok(event)
    }

    pub fn finish(&mut self) -> Option<Json> {
        if self.previous_hash.is_some() && !self.changes.is_empty() {
            let mut event = self.flush();
            event["operation"] = json!("state_finalize");
            Some(event)
        } else {
            None
        }
    }

    fn flush(&mut self) -> Json {
        let resulting = self.hash();
        let previous = self.previous_hash.replace(resulting.clone());
        json!({
            "frame_id": self.frame_id,
            "parent_event_id": self.previous_event_id,
            "previous_state_hash": previous,
            "changes": std::mem::take(&mut self.changes),
            "resulting_state_hash": resulting,
        })
    }

    pub fn assign(&mut self, name: &str, previous: Option<&Value>, value: &Value) {
        if !visible(name) {
            return;
        }
        let path = vec![name.to_owned()];
        if let Some(previous) = previous {
            self.register(previous, &path, false);
        }
        self.replace(&path, to_json(value));
        self.register(value, &path, true);
    }

    /// A mutable object can be reachable through several bindings, nested
    /// fields, or suspended callers. The identity index updates every alias
    /// without scanning unrelated rows on each write.
    pub fn mutation(
        &mut self,
        owner: &Value,
        suffix: &[String],
        previous: Option<&Value>,
        value: &Value,
    ) {
        let paths = identity(owner)
            .and_then(|id| self.aliases.get(&id))
            .cloned()
            .unwrap_or_default();
        for mut path in paths {
            path.extend_from_slice(suffix);
            if let Some(previous) = previous {
                self.register(previous, &path, false);
            }
            self.replace(&path, to_json(value));
            self.register(value, &path, true);
        }
    }

    fn register(&mut self, value: &Value, path: &Path, add: bool) {
        if let Some(id) = identity(value) {
            if add {
                let paths = self.aliases.entry(id).or_default();
                if !paths.insert(path.clone()) {
                    return;
                }
            } else if let Some(paths) = self.aliases.get_mut(&id) {
                if !paths.remove(path) {
                    return;
                }
                if paths.is_empty() {
                    self.aliases.remove(&id);
                }
            } else {
                return;
            }
        }
        match value {
            Value::Array(items) => {
                for (index, item) in items.borrow().iter().enumerate() {
                    let mut child = path.clone();
                    child.push(index.to_string());
                    self.register(item, &child, add);
                }
            }
            Value::Struct(value) => {
                for (name, field) in value.fields.borrow().iter() {
                    let mut child = path.clone();
                    child.extend(["fields".to_owned(), name.clone()]);
                    self.register(field, &child, add);
                }
            }
            Value::Optional(Some(value)) => {
                let mut child = path.clone();
                child.push("value".to_owned());
                self.register(value, &child, add);
            }
            _ => {}
        }
    }

    fn replace(&mut self, path: &Path, value: Json) {
        let old = if path.len() == 1 {
            self.state.insert(path[0].clone(), value)
        } else {
            let root = self.state.get_mut(&path[0]).expect("registered trace root");
            let target = root
                .pointer_mut(&pointer(&path[1..]))
                .expect("registered trace path");
            Some(std::mem::replace(target, value))
        };
        let current = if path.len() == 1 {
            &self.state[&path[0]]
        } else {
            self.state[&path[0]]
                .pointer(&pointer(&path[1..]))
                .expect("registered trace path")
        };
        if old.as_ref() == Some(current) {
            return;
        }
        let mut contribution = [0u8; 32];
        if let Some(old) = &old {
            hash_tree(path, old, &mut contribution);
        }
        hash_tree(path, current, &mut contribution);
        xor(&mut self.digest, &contribution);
        if self.previous_hash.is_some() {
            diff(old.as_ref(), Some(current), path, &mut self.changes);
        }
    }
}

fn xor(target: &mut [u8; 32], value: &[u8; 32]) {
    for (target, value) in target.iter_mut().zip(value) {
        *target ^= value;
    }
}

fn hash_tree(path: &[String], value: &Json, result: &mut [u8; 32]) {
    let marker = match value {
        Json::Array(items) => json!({"array_length": items.len()}),
        Json::Object(_) => json!({"object": true}),
        scalar => scalar.clone(),
    };
    let encoded = serde_json::to_vec(&(path, marker)).expect("JSON state leaf");
    xor(result, &Sha256::digest(encoded).into());
    match value {
        Json::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                let mut child = path.to_vec();
                child.push(index.to_string());
                hash_tree(&child, item, result);
            }
        }
        Json::Object(fields) => {
            for (name, item) in fields {
                let mut child = path.to_vec();
                child.push(name.clone());
                hash_tree(&child, item, result);
            }
        }
        _ => {}
    }
}

fn diff(old: Option<&Json>, new: Option<&Json>, path: &[String], changes: &mut Vec<Json>) {
    if old == new {
        return;
    }
    match (old, new) {
        (Some(Json::Object(a)), Some(Json::Object(b))) => {
            let keys: std::collections::BTreeSet<_> = a.keys().chain(b.keys()).collect();
            for key in keys {
                let mut child = path.to_vec();
                child.push(key.clone());
                diff(a.get(key), b.get(key), &child, changes);
            }
        }
        (Some(Json::Array(a)), Some(Json::Array(b))) => {
            for index in 0..a.len().min(b.len()) {
                let mut child = path.to_vec();
                child.push(index.to_string());
                diff(a.get(index), b.get(index), &child, changes);
            }
            for index in (b.len()..a.len()).rev() {
                let mut child = path.to_vec();
                child.push(index.to_string());
                diff(a.get(index), None, &child, changes);
            }
            for index in a.len()..b.len() {
                let mut child = path.to_vec();
                child.push(index.to_string());
                diff(None, b.get(index), &child, changes);
            }
        }
        (Some(a), Some(b))
            if !a.is_array() && !a.is_object() && !b.is_array() && !b.is_object() =>
        {
            changes
                .push(json!({"operation": "replace", "path": pointer(path), "old": a, "new": b}));
        }
        _ => {
            // Containers are represented by empty nodes plus child edits;
            // even replacing an Array never embeds its complete snapshot.
            if let Some(old) = old {
                children(old, path, changes, false);
                changes.push(json!({"operation": "remove", "path": pointer(path), "old": empty(old), "new": null}));
            }
            if let Some(new) = new {
                changes.push(json!({"operation": "add", "path": pointer(path), "old": null, "new": empty(new)}));
                children(new, path, changes, true);
            }
        }
    }
}

fn empty(value: &Json) -> Json {
    match value {
        Json::Array(_) => json!([]),
        Json::Object(_) => json!({}),
        _ => value.clone(),
    }
}

fn children(value: &Json, path: &[String], changes: &mut Vec<Json>, add: bool) {
    let items: Vec<_> = match value {
        Json::Array(items) => items
            .iter()
            .enumerate()
            .map(|(i, value)| (i.to_string(), value))
            .collect(),
        Json::Object(fields) => {
            let mut items: Vec<_> = fields
                .iter()
                .map(|(key, value)| (key.clone(), value))
                .collect();
            items.sort_by(|a, b| a.0.cmp(&b.0));
            items
        }
        _ => Vec::new(),
    };
    let items: Box<dyn Iterator<Item = _>> = if add {
        Box::new(items.into_iter())
    } else {
        Box::new(items.into_iter().rev())
    };
    for (key, value) in items {
        let mut child = path.to_vec();
        child.push(key);
        if add {
            diff(None, Some(value), &child, changes);
        } else {
            diff(Some(value), None, &child, changes);
        }
    }
}
