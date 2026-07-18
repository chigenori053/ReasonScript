use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

pub fn canonical_value(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut keys: Vec<_> = map.keys().collect();
            keys.sort();
            let mut result = serde_json::Map::new();
            for key in keys {
                result.insert(key.clone(), canonical_value(&map[key]));
            }
            Value::Object(result)
        }
        Value::Array(items) => Value::Array(items.iter().map(canonical_value).collect()),
        _ => value.clone(),
    }
}

pub fn canonical_json<T: Serialize>(value: &T) -> Result<String, serde_json::Error> {
    let value = serde_json::to_value(value)?;
    serde_json::to_string(&canonical_value(&value))
}

pub fn pretty_json<T: Serialize>(value: &T) -> Result<String, serde_json::Error> {
    let value = serde_json::to_value(value)?;
    Ok(serde_json::to_string_pretty(&canonical_value(&value))? + "\n")
}

pub fn checksum<T: Serialize>(value: &T) -> Result<String, serde_json::Error> {
    let payload = canonical_json(value)?;
    let digest = Sha256::digest(payload.as_bytes());
    Ok(format!("sha256:{digest:x}"))
}
