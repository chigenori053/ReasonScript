//! `.rstensor` file encode/decode, matching `frontend/tensor/runtime.py`'s
//! `_encode_tensor_file` / `_decode_tensor_file` / `_pack_tensor_data` /
//! `_unpack_tensor_data` byte-for-byte: magic `RSNTNSR1`, a little-endian
//! `u32` header length, a JSON header, then the packed body. The header
//! is read generically (any valid JSON with the right keys), so this
//! doesn't need to reproduce Python's exact `json.dumps` formatting to
//! round-trip with it -- see `_decode_tensor_file` on the Python side,
//! which does `json.loads(...)`, not a byte comparison.

use sha2::{Digest, Sha256};

use crate::dtype::Dtype;
use crate::error::{Result, TensorCoreError};
use crate::shape::product;
use crate::store::TensorData;

const MAGIC: &[u8; 8] = b"RSNTNSR1";
pub const PROFILE: &str = "reasonscript-tensor-file/1.0";

pub fn encode(tensor: &TensorData) -> (Vec<u8>, String) {
    let body = pack(tensor);
    let digest = Sha256::digest(&body);
    let checksum = hex(&digest);
    let header = serde_json::json!({
        "byte_size": body.len(),
        "dtype": tensor.dtype.name(),
        "payload_sha256": checksum,
        "profile": PROFILE,
        "shape": tensor.shape,
    });
    let header_bytes = serde_json::to_vec(&header).expect("header always serializes");
    let mut payload = Vec::with_capacity(8 + 4 + header_bytes.len() + body.len());
    payload.extend_from_slice(MAGIC);
    payload.extend_from_slice(&(header_bytes.len() as u32).to_le_bytes());
    payload.extend_from_slice(&header_bytes);
    payload.extend_from_slice(&body);
    (payload, checksum)
}

pub fn decode(payload: &[u8]) -> Result<TensorData> {
    if payload.len() < 12 || &payload[..8] != MAGIC {
        return Err(TensorCoreError::new("TIO-003", "invalid Tensor file magic"));
    }
    let header_size = u32::from_le_bytes(payload[8..12].try_into().unwrap()) as usize;
    if header_size > payload.len().saturating_sub(12) {
        return Err(TensorCoreError::new(
            "TIO-003",
            "invalid Tensor file header",
        ));
    }
    let header: serde_json::Value = serde_json::from_slice(&payload[12..12 + header_size])
        .map_err(|_| TensorCoreError::new("TIO-003", "invalid Tensor file header"))?;
    let body = &payload[12 + header_size..];

    let profile = header.get("profile").and_then(|v| v.as_str());
    let byte_size = header.get("byte_size").and_then(|v| v.as_u64());
    let payload_sha256 = header.get("payload_sha256").and_then(|v| v.as_str());
    let digest = hex(&Sha256::digest(body));
    if profile != Some(PROFILE)
        || byte_size != Some(body.len() as u64)
        || payload_sha256 != Some(digest.as_str())
    {
        return Err(TensorCoreError::new(
            "TIO-004",
            "Tensor file checksum or size mismatch",
        ));
    }

    let dtype_name = header
        .get("dtype")
        .and_then(|v| v.as_str())
        .ok_or_else(|| TensorCoreError::new("TSF-002", "missing dtype in Tensor file header"))?;
    let dtype = Dtype::parse(dtype_name)?;
    let shape: Vec<usize> = header
        .get("shape")
        .and_then(|v| v.as_array())
        .ok_or_else(|| TensorCoreError::new("TSF-003", "missing shape in Tensor file header"))?
        .iter()
        .filter_map(|v| v.as_u64())
        .map(|v| v as usize)
        .collect();

    let data = unpack(dtype, body)?;
    if data.len() != product(&shape) {
        return Err(TensorCoreError::new(
            "TSF-003",
            "Tensor file shape mismatch",
        ));
    }
    Ok(TensorData { shape, dtype, data })
}

fn pack(tensor: &TensorData) -> Vec<u8> {
    let width = tensor.dtype.byte_width();
    let mut body = Vec::with_capacity(tensor.data.len() * width);
    for &value in &tensor.data {
        match tensor.dtype {
            Dtype::Bool => body.push(if value != 0.0 { 1 } else { 0 }),
            Dtype::I32 => body.extend_from_slice(&(value as i32).to_le_bytes()),
            Dtype::I64 => body.extend_from_slice(&(value as i64).to_le_bytes()),
            Dtype::F32 => body.extend_from_slice(&(value as f32).to_le_bytes()),
            Dtype::F64 => body.extend_from_slice(&value.to_le_bytes()),
        }
    }
    body
}

fn unpack(dtype: Dtype, body: &[u8]) -> Result<Vec<f64>> {
    let width = dtype.byte_width();
    if width == 0 || !body.len().is_multiple_of(width) {
        return Err(TensorCoreError::new(
            "TIO-003",
            "Tensor payload alignment is invalid",
        ));
    }
    let mut data = Vec::with_capacity(body.len() / width);
    for chunk in body.chunks_exact(width) {
        let value = match dtype {
            Dtype::Bool => (chunk[0] != 0) as u8 as f64,
            Dtype::I32 => i32::from_le_bytes(chunk.try_into().unwrap()) as f64,
            Dtype::I64 => i64::from_le_bytes(chunk.try_into().unwrap()) as f64,
            Dtype::F32 => f32::from_le_bytes(chunk.try_into().unwrap()) as f64,
            Dtype::F64 => f64::from_le_bytes(chunk.try_into().unwrap()),
        };
        data.push(value);
    }
    Ok(data)
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}
