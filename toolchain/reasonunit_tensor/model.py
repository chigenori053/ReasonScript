"""RUO-T1 canonical Tensor representation, validation, and conversion."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import struct
import tempfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from toolchain.reasonunit_object.model import canonicalize

PROFILE = "ruo.tensor/1.0"
PAYLOAD_PROFILE = "ruo.payload.tensor/1"
MEDIA_TYPE = "application/vnd.reasonscript.ruo-tensor"
MASK_MEDIA_TYPE = "application/vnd.reasonscript.ruo-tensor-mask"
VALIDITY_STATES = {"invalid": 0, "valid": 1, "unknown": 2, "not_loaded": 3, "redacted": 4}
DTYPES: dict[str, dict[str, Any]] = {
    "bool": {"width": 1, "kind": "bool"},
    "int8": {"width": 1, "kind": "int", "signed": True},
    "uint8": {"width": 1, "kind": "int", "signed": False},
    "int16": {"width": 2, "kind": "int", "signed": True},
    "uint16": {"width": 2, "kind": "int", "signed": False},
    "int32": {"width": 4, "kind": "int", "signed": True},
    "uint32": {"width": 4, "kind": "int", "signed": False},
    "int64": {"width": 8, "kind": "int", "signed": True},
    "uint64": {"width": 8, "kind": "int", "signed": False},
    "float16": {"width": 2, "kind": "float", "format": "e"},
    "bfloat16": {"width": 2, "kind": "bfloat"},
    "float32": {"width": 4, "kind": "float", "format": "f"},
    "float64": {"width": 8, "kind": "float", "format": "d"},
    "complex64": {"width": 8, "kind": "complex", "format": "f"},
    "complex128": {"width": 16, "kind": "complex", "format": "d"},
}
DEFAULT_LIMITS = {
    "rank": 32, "dimension": 2**31 - 1, "elements": 10_000_000,
    "logical_bytes": 256_000_000, "inline_elements": 4096, "inline_bytes": 65536,
    "resource_bytes": 2_000_000_000, "chunks": 100_000, "nnz": 10_000_000,
    "mapping_entries": 10_000_000, "mask_bytes": 10_000_000,
    "conversion_expansion": 10_000_000, "selector_expansion": 10_000_000,
    "diagnostics": 1000,
}


class TensorError(ValueError):
    def __init__(self, code: str, message: str, *, stage: str, tensor_id: str | None = None,
                 resource_id: str | None = None, metadata: dict[str, Any] | None = None):
        super().__init__(message); self.code = code; self.stage = stage; self.tensor_id = tensor_id
        self.resource_id = resource_id; self.metadata = metadata or {}

    def diagnostic(self) -> dict[str, Any]:
        result = {"code": self.code, "severity": "ERROR", "stage": self.stage, "message": str(self)}
        if self.tensor_id: result["tensor_id"] = self.tensor_id
        if self.resource_id: result["resource_id"] = self.resource_id
        result.update(self.metadata); return result


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def shape_product(shape: Any, *, limit: int = 2**63 - 1) -> int:
    if not isinstance(shape, list): raise TensorError("RUO-T1-004", "Shape must be an array.", stage="shape")
    result = 1
    for dimension in shape:
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 0:
            raise TensorError("RUO-T1-004", "Dimensions must be non-negative integers.", stage="shape")
        if dimension and result > limit // dimension:
            raise TensorError("RUO-T1-004", "Shape product overflow.", stage="shape")
        result *= dimension
    return result


def _positive_zero(value: float) -> float:
    if not math.isfinite(value): raise TensorError("RUO-T1-007", "Non-finite Tensor values are prohibited.", stage="scalar")
    return 0.0 if value == 0.0 else value


def encode_scalar(dtype: str, value: Any) -> bytes:
    spec = DTYPES.get(dtype)
    if spec is None: raise TensorError("RUO-T1-003", f"Unknown dtype: {dtype}", stage="dtype")
    try:
        if spec["kind"] == "bool":
            if not isinstance(value, bool): raise ValueError("Boolean value required")
            return bytes([int(value)])
        if spec["kind"] == "int":
            if isinstance(value, bool) or not isinstance(value, int): raise ValueError("Integer value required")
            return value.to_bytes(spec["width"], "little", signed=spec["signed"])
        if spec["kind"] == "float": return struct.pack("<" + spec["format"], _positive_zero(float(value)))
        if spec["kind"] == "bfloat":
            packed = struct.pack("<f", _positive_zero(float(value)))
            bits = int.from_bytes(packed, "little"); upper = bits >> 16
            lower = bits & 0xFFFF
            if lower > 0x8000 or (lower == 0x8000 and upper & 1): upper = (upper + 1) & 0xFFFF
            return upper.to_bytes(2, "little")
        if isinstance(value, complex): real, imaginary = value.real, value.imag
        elif isinstance(value, (list, tuple)) and len(value) == 2: real, imaginary = value
        else: raise ValueError("Complex value must have real and imaginary components")
        return struct.pack("<" + spec["format"] * 2, _positive_zero(float(real)), _positive_zero(float(imaginary)))
    except (OverflowError, struct.error, TypeError, ValueError) as error:
        if isinstance(error, TensorError): raise
        raise TensorError("RUO-T1-007", f"Value is not representable as {dtype}: {error}", stage="scalar") from error


def decode_scalar(dtype: str, data: bytes) -> Any:
    spec = DTYPES.get(dtype)
    if spec is None: raise TensorError("RUO-T1-003", f"Unknown dtype: {dtype}", stage="dtype")
    if len(data) != spec["width"]: raise TensorError("RUO-T1-007", "Scalar byte width mismatch.", stage="scalar")
    if spec["kind"] == "bool":
        if data not in {b"\x00", b"\x01"}: raise TensorError("RUO-T1-007", "Boolean byte must be 0x00 or 0x01.", stage="scalar")
        return data == b"\x01"
    if spec["kind"] == "int": return int.from_bytes(data, "little", signed=spec["signed"])
    if spec["kind"] == "bfloat": value = struct.unpack("<f", b"\x00\x00" + data)[0]
    elif spec["kind"] == "float": value = struct.unpack("<" + spec["format"], data)[0]
    else:
        values = struct.unpack("<" + spec["format"] * 2, data)
        if any(not math.isfinite(item) or (item == 0 and math.copysign(1, item) < 0) for item in values):
            raise TensorError("RUO-T1-007", "Complex components must be finite normalized values.", stage="scalar")
        return [values[0], values[1]]
    if not math.isfinite(value) or (value == 0 and math.copysign(1, value) < 0):
        raise TensorError("RUO-T1-007", "Float must be finite and negative zero normalized.", stage="scalar")
    return value


def encode_values(dtype: str, values: Iterable[Any]) -> bytes:
    return b"".join(encode_scalar(dtype, value) for value in values)


def decode_values(dtype: str, data: bytes) -> list[Any]:
    spec = DTYPES.get(dtype)
    if spec is None: raise TensorError("RUO-T1-003", f"Unknown dtype: {dtype}", stage="dtype")
    if len(data) % spec["width"]: raise TensorError("RUO-T1-007", "Dense resource byte size is not dtype-aligned.", stage="dense")
    return [decode_scalar(dtype, data[index:index + spec["width"]]) for index in range(0, len(data), spec["width"])]


def encode_mask(states: Iterable[str]) -> bytes:
    try: return bytes(VALIDITY_STATES[state] for state in states)
    except (KeyError, TypeError) as error: raise TensorError("RUO-T1-013", "Unknown validity state.", stage="mask") from error


def decode_mask(data: bytes) -> list[str]:
    reverse = {value: key for key, value in VALIDITY_STATES.items()}
    try: return [reverse[value] for value in data]
    except KeyError as error: raise TensorError("RUO-T1-013", "Invalid validity mask byte.", stage="mask") from error


def _inline_bytes(dtype: str, values: Any) -> bytes:
    if not isinstance(values, list): raise TensorError("RUO-T1-010", "Inline values must be flattened in an array.", stage="inline")
    kind, width = DTYPES[dtype]["kind"], DTYPES[dtype]["width"]
    if kind in {"float", "bfloat", "complex"}:
        result = bytearray()
        for value in values:
            if not isinstance(value, str) or len(value) != width * 2 or value.lower() != value:
                raise TensorError("RUO-T1-010", "Inline float/complex values require lowercase canonical hex bytes.", stage="inline")
            try: raw = bytes.fromhex(value)
            except ValueError as error: raise TensorError("RUO-T1-010", "Invalid inline hexadecimal value.", stage="inline") from error
            decode_scalar(dtype, raw); result.extend(raw)
        return bytes(result)
    return encode_values(dtype, values)


def _body(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    if payload.get("profile_id") == PAYLOAD_PROFILE:
        return payload.get("value", payload.get("body", {})), payload.get("payload_id")
    return payload, payload.get("payload_id")


def _safe_locator(locator: Any) -> bool:
    if not isinstance(locator, str) or not locator or "\\" in locator or "\x00" in locator: return False
    pure = PurePosixPath(locator)
    return not pure.is_absolute() and all(part not in {"", ".", ".."} for part in pure.parts) and ":" not in pure.parts[0]


def _axis_contract(body: dict[str, Any], shape: list[int], limits: dict[str, int]) -> None:
    axes = body.get("axes")
    if not isinstance(axes, list) or len(axes) != len(shape): raise TensorError("RUO-T1-005", "Axes must have rank entries.", stage="axis")
    for ordinal, (axis, dimension) in enumerate(zip(axes, shape)):
        if not isinstance(axis, dict) or axis.get("ordinal") != ordinal or axis.get("size") != dimension:
            raise TensorError("RUO-T1-005", "Axis ordinal or dimension mismatch.", stage="axis")
        mapping = axis.get("identity_mapping")
        if mapping is not None:
            ids = mapping.get("ordered_ids", []) if isinstance(mapping, dict) else []
            partial = bool(mapping.get("partial", False)) if isinstance(mapping, dict) else False
            if len(ids) > limits["mapping_entries"] or (not partial and len(ids) != dimension):
                raise TensorError("RUO-T1-006", "Identity mapping length mismatch or limit exceeded.", stage="mapping")
            if any(not isinstance(item, str) or ":" not in item or item.isdigit() for item in ids):
                raise TensorError("RUO-T1-006", "Mappings require stable namespaced IDs, not Tensor indexes.", stage="mapping")
            policy = axis.get("duplicate_policy", mapping.get("duplicate_policy", "forbidden"))
            if policy == "forbidden" and len(ids) != len(set(ids)):
                raise TensorError("RUO-T1-006", "Duplicate stable IDs are forbidden.", stage="mapping")
            expected = mapping_digest(body.get("payload_id", ""), ordinal, mapping)
            if mapping.get("mapping_digest") not in {None, expected}: raise TensorError("RUO-T1-006", "Mapping digest mismatch.", stage="mapping")


def mapping_digest(tensor_id: str, ordinal: int, mapping: dict[str, Any]) -> str:
    normalized = {key: mapping.get(key) for key in ("mapping_version", "ordered_ids", "uniqueness", "source_object_revision", "partial", "included_positions") if key in mapping}
    return _sha(canonicalize({"tensor_id": tensor_id, "axis_ordinal": ordinal, "mapping": normalized}).encode())


def _chunks(chunks: Any, byte_size: int, data: bytes | None, limits: dict[str, int]) -> None:
    if chunks in (None, []): return
    if not isinstance(chunks, list) or len(chunks) > limits["chunks"]: raise TensorError("RUO-T1-012", "Invalid chunk list or limit exceeded.", stage="chunk")
    offset = 0; element_start = 0; axis_end = 0
    for index, chunk in enumerate(chunks):
        if chunk.get("index") != index or chunk.get("byte_offset") != offset or chunk.get("logical_element_start") != element_start:
            raise TensorError("RUO-T1-012", "Chunks must be ordered, contiguous, and non-overlapping.", stage="chunk")
        if "axis0_start" in chunk and (chunk.get("axis0_start") != axis_end or not isinstance(chunk.get("axis0_end"), int) or chunk.get("axis0_end") < axis_end):
            raise TensorError("RUO-T1-012", "Chunk axis-0 coverage is malformed.", stage="chunk")
        size = chunk.get("byte_size"); count = chunk.get("logical_element_count")
        if not isinstance(size, int) or size < 0 or not isinstance(count, int) or count < 0:
            raise TensorError("RUO-T1-012", "Invalid chunk range.", stage="chunk")
        if data is not None and _sha(data[offset:offset + size]) != chunk.get("sha256"):
            raise TensorError("RUO-T1-012", "Chunk digest mismatch.", stage="chunk", metadata={"chunk_index": index})
        offset += size; element_start += count; axis_end = chunk.get("axis0_end", axis_end)
    if offset != byte_size: raise TensorError("RUO-T1-012", "Chunks do not exactly cover resource.", stage="chunk")


def _dense(body: dict[str, Any], data: bytes | None, count: int, limits: dict[str, int]) -> bytes | None:
    storage = body.get("storage", {}); expected = count * DTYPES[body["dtype"]]["width"]
    for key, value in {"layout": "row_major", "byte_order": "little", "contiguous": True, "offset_bytes": 0}.items():
        if storage.get(key) != value: raise TensorError("RUO-T1-007", "Canonical dense layout contract mismatch.", stage="dense")
    if expected > limits["logical_bytes"]: raise TensorError("RUO-T1-023", "Logical Tensor byte limit exceeded.", stage="limits")
    if data is not None:
        if len(data) != expected: raise TensorError("RUO-T1-007", "Dense resource size mismatch.", stage="dense")
        decode_values(body["dtype"], data)
    return data


def _coo(body: dict[str, Any], count: int, limits: dict[str, int]) -> list[Any]:
    storage = body.get("storage", {}); rank = body["rank"]; shape = body["shape"]
    nnz, coordinates, values = storage.get("nnz"), storage.get("coordinates"), storage.get("values")
    if storage.get("index_dtype") != "uint64" or storage.get("duplicate_coordinate_policy") != "forbidden" or not isinstance(nnz, int) or nnz < 0 or nnz > limits["nnz"]:
        raise TensorError("RUO-T1-008", "Invalid COO profile, duplicate policy, or nnz.", stage="coo")
    if not isinstance(coordinates, list) or len(coordinates) != nnz or not isinstance(values, list) or len(values) != nnz:
        raise TensorError("RUO-T1-008", "COO coordinate/value count mismatch.", stage="coo")
    previous = None
    for coordinate in coordinates:
        if not isinstance(coordinate, list) or len(coordinate) != rank or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 or v >= shape[i] for i, v in enumerate(coordinate)):
            raise TensorError("RUO-T1-008", "COO coordinate is malformed or out of range.", stage="coo")
        key = tuple(coordinate)
        if previous is not None and key <= previous: raise TensorError("RUO-T1-008", "COO coordinates must be sorted and unique.", stage="coo")
        previous = key
    encoded = [encode_scalar(body["dtype"], value) for value in values]
    if storage.get("explicit_zero_policy") != "preserve" and any(all(byte == 0 for byte in item) for item in encoded):
        raise TensorError("RUO-T1-008", "Explicit zero requires preserve policy.", stage="coo")
    dense = [zero_value(body["dtype"])] * count
    for coordinate, value in zip(coordinates, values): dense[flat_index(coordinate, shape)] = value
    return dense


def _csr(body: dict[str, Any], count: int, limits: dict[str, int]) -> list[Any]:
    storage = body.get("storage", {}); shape = body["shape"]
    if body["rank"] != 2: raise TensorError("RUO-T1-009", "CSR requires rank 2.", stage="csr")
    nnz, pointers, columns, values = storage.get("nnz"), storage.get("row_pointers"), storage.get("column_indices"), storage.get("values")
    if storage.get("row_pointer_dtype") != "uint64" or storage.get("column_index_dtype") != "uint64" or storage.get("duplicate_column_policy") != "forbidden" or not isinstance(nnz, int) or nnz < 0 or nnz > limits["nnz"]:
        raise TensorError("RUO-T1-009", "Invalid CSR profile or nnz.", stage="csr")
    if not isinstance(pointers, list) or len(pointers) != shape[0] + 1 or pointers[:1] != [0] or pointers[-1:] != [nnz] or any(a > b for a, b in zip(pointers, pointers[1:])):
        raise TensorError("RUO-T1-009", "Invalid CSR row pointers.", stage="csr")
    if not isinstance(columns, list) or not isinstance(values, list) or len(columns) != nnz or len(values) != nnz:
        raise TensorError("RUO-T1-009", "CSR column/value count mismatch.", stage="csr")
    dense = [zero_value(body["dtype"])] * count
    for row in range(shape[0]):
        row_columns = columns[pointers[row]:pointers[row + 1]]
        if any(isinstance(col, bool) or not isinstance(col, int) or col < 0 or col >= shape[1] for col in row_columns) or any(a >= b for a, b in zip(row_columns, row_columns[1:])):
            raise TensorError("RUO-T1-009", "CSR columns must be in range and strictly increasing.", stage="csr")
        for index in range(pointers[row], pointers[row + 1]):
            encoded = encode_scalar(body["dtype"], values[index])
            if storage.get("explicit_zero_policy") != "preserve" and all(byte == 0 for byte in encoded): raise TensorError("RUO-T1-009", "Explicit zero requires preserve policy.", stage="csr")
            dense[row * shape[1] + columns[index]] = values[index]
    return dense


def zero_value(dtype: str) -> Any:
    if dtype == "bool": return False
    if DTYPES[dtype]["kind"] == "complex": return [0.0, 0.0]
    return 0.0 if DTYPES[dtype]["kind"] in {"float", "bfloat"} else 0


def flat_index(coordinate: list[int], shape: list[int]) -> int:
    result = 0
    for value, dimension in zip(coordinate, shape): result = result * dimension + value
    return result


def dense_values(payload: dict[str, Any], *, resource_bytes: bytes | None = None) -> list[Any]:
    body, _ = _body(payload); rep, storage = body.get("representation"), body.get("storage", {})
    if rep == "inline": return decode_values(body["dtype"], _inline_bytes(body["dtype"], storage.get("values")))
    if rep == "dense_resource":
        if resource_bytes is None: raise TensorError("RUO-T1-011", "External Tensor resource bytes are required.", stage="resource")
        return decode_values(body["dtype"], resource_bytes)
    if rep == "coo_resource": return _coo(body, body["element_count"], DEFAULT_LIMITS)
    if rep == "csr_resource": return _csr(body, body["element_count"], DEFAULT_LIMITS)
    raise TensorError("RUO-T1-002", "Unknown Tensor representation.", stage="payload")


def normalized_logical(payload: dict[str, Any], *, resource_bytes: bytes | None = None) -> dict[str, Any]:
    body, tensor_id = _body(payload)
    values = dense_values(body, resource_bytes=resource_bytes)
    semantic_axes = copy.deepcopy(body.get("axes", []))
    for axis in semantic_axes:
        mapping = axis.get("identity_mapping")
        if isinstance(mapping, dict): mapping.pop("mapping_digest", None)
    return {"tensor_profile": body.get("tensor_profile"), "dtype": body.get("dtype"), "rank": body.get("rank"), "shape": body.get("shape"), "axes": semantic_axes, "values_hex": [encode_scalar(body["dtype"], value).hex() for value in values], "validity": body.get("validity"), "unit": body.get("unit"), "reference_frame": body.get("reference_frame"), "explicit_zero_policy": body.get("storage", {}).get("explicit_zero_policy", "forbidden"), "critical_extensions": {key: value for key, value in body.get("extensions", {}).items() if isinstance(value, dict) and value.get("critical")}}


def logical_digest(payload: dict[str, Any], *, resource_bytes: bytes | None = None) -> str:
    return _sha(canonicalize(normalized_logical(payload, resource_bytes=resource_bytes)).encode())


def validate_tensor(payload: dict[str, Any], *, resource_bytes: bytes | None = None,
                    mask_bytes: bytes | None = None, limits: dict[str, int] | None = None,
                    require_digest: bool = True) -> dict[str, Any]:
    limits = {**DEFAULT_LIMITS, **(limits or {})}; body, envelope_id = _body(payload); tensor_id = envelope_id or body.get("payload_id")
    try:
        if not isinstance(body, dict) or body.get("tensor_profile") != PROFILE:
            raise TensorError("RUO-T1-002", "Invalid Tensor profile.", stage="payload", tensor_id=tensor_id)
        if envelope_id and (not envelope_id.startswith("ruo:payload:") or ("profile_id" in payload and payload.get("profile_id") != PAYLOAD_PROFILE)):
            raise TensorError("RUO-T1-002", "Invalid Tensor Payload identity.", stage="identity", tensor_id=tensor_id)
        if body.get("value_presence") not in {"present", "external", "not_loaded", "unknown", "redacted"}:
            raise TensorError("RUO-T1-002", "Invalid Tensor value presence.", stage="payload", tensor_id=tensor_id)
        for namespace, extension in body.get("extensions", {}).items():
            if isinstance(extension, dict) and extension.get("critical") and not str(namespace).startswith("ruo.tensor."):
                raise TensorError("RUO-T1-022", "Unknown critical Tensor extension.", stage="version", tensor_id=tensor_id)
        dtype = body.get("dtype")
        if dtype not in DTYPES: raise TensorError("RUO-T1-003", "Unknown or invalid dtype.", stage="dtype", tensor_id=tensor_id)
        rank, shape = body.get("rank"), body.get("shape")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0 or rank > limits["rank"] or not isinstance(shape, list) or rank != len(shape):
            raise TensorError("RUO-T1-004", "Rank and shape mismatch or rank limit exceeded.", stage="shape", tensor_id=tensor_id)
        if any(dimension > limits["dimension"] for dimension in shape if isinstance(dimension, int)):
            raise TensorError("RUO-T1-023", "Dimension limit exceeded.", stage="limits", tensor_id=tensor_id)
        count = shape_product(shape)
        if count != body.get("element_count"): raise TensorError("RUO-T1-004", "Element count mismatch.", stage="shape", tensor_id=tensor_id)
        if count > limits["elements"]: raise TensorError("RUO-T1-023", "Element count limit exceeded.", stage="limits", tensor_id=tensor_id)
        _axis_contract(body, shape, limits)
        representation = body.get("representation")
        logical_bytes: bytes | None = None
        if representation == "inline":
            logical_bytes = _inline_bytes(dtype, body.get("storage", {}).get("values"))
            if count > limits["inline_elements"] or len(logical_bytes) > limits["inline_bytes"]: raise TensorError("RUO-T1-010", "Inline Tensor limit exceeded.", stage="inline")
            if len(logical_bytes) != count * DTYPES[dtype]["width"]: raise TensorError("RUO-T1-010", "Inline value count mismatch.", stage="inline")
        elif representation == "dense_resource":
            storage = body.get("storage", {}); resource_id = storage.get("resource_id")
            if not isinstance(resource_id, str) or not resource_id.startswith("ruo:resource:") or resource_id in {tensor_id, body.get("logical_digest")} or storage.get("media_type") != MEDIA_TYPE or not _safe_locator(storage.get("locator")):
                raise TensorError("RUO-T1-011", "Invalid or ambiguous Tensor Resource identity, media type, or locator.", stage="resource", tensor_id=tensor_id, resource_id=resource_id)
            logical_bytes = _dense(body, resource_bytes, count, limits)
        elif representation == "coo_resource": _coo(body, count, limits)
        elif representation == "csr_resource": _csr(body, count, limits)
        else: raise TensorError("RUO-T1-002", "Unknown Tensor representation.", stage="payload")
        storage = body.get("storage", {})
        if resource_bytes is not None:
            if len(resource_bytes) > limits["resource_bytes"]: raise TensorError("RUO-T1-023", "Resource byte limit exceeded.", stage="limits")
            if storage.get("byte_size") not in {None, len(resource_bytes)} or storage.get("sha256") not in {None, _sha(resource_bytes)}:
                raise TensorError("RUO-T1-011", "Tensor Resource size or digest mismatch.", stage="resource")
            _chunks(storage.get("chunks"), len(resource_bytes), resource_bytes, limits)
        validity = body.get("validity")
        if not isinstance(validity, dict) or validity.get("status") not in {"complete", "masked", "partial", "unknown"}:
            raise TensorError("RUO-T1-013", "Invalid validity contract.", stage="mask")
        inline_mask = validity.get("states")
        if inline_mask is not None:
            if len(inline_mask) != count: raise TensorError("RUO-T1-013", "Validity mask shape mismatch.", stage="mask")
            encode_mask(inline_mask)
        if mask_bytes is not None:
            if len(mask_bytes) != count or len(mask_bytes) > limits["mask_bytes"]: raise TensorError("RUO-T1-013", "External mask byte size mismatch.", stage="mask")
            decode_mask(mask_bytes)
        if validity.get("status") == "complete" and ((inline_mask and any(state != "valid" for state in inline_mask)) or (mask_bytes and any(byte != 1 for byte in mask_bytes))):
            raise TensorError("RUO-T1-016", "Partial or masked Tensor cannot claim completeness.", stage="partial")
        if logical_bytes is not None or representation in {"coo_resource", "csr_resource"}:
            observed = logical_digest(body, resource_bytes=resource_bytes)
            if require_digest and body.get("logical_digest") != observed: raise TensorError("RUO-T1-014", "Logical Tensor digest mismatch.", stage="digest", metadata={"expected": body.get("logical_digest"), "observed": observed})
        else: observed = body.get("logical_digest")
        return {"ok": True, "tensor_id": tensor_id, "dtype": dtype, "shape": shape, "representation": representation, "logical_digest": observed, "resource_sha256": _sha(resource_bytes) if resource_bytes is not None else storage.get("sha256"), "mapping_status": "VALID", "integrity_status": "VALID" if resource_bytes is not None or representation != "dense_resource" else "NOT_EVALUATED", "semantic_status": "VALID" if validity.get("status") == "complete" else "INDETERMINATE", "diagnostics": []}
    except TensorError as error:
        if tensor_id and not error.tensor_id: error.tensor_id = tensor_id
        return {"ok": False, "tensor_id": tensor_id, "dtype": body.get("dtype") if isinstance(body, dict) else None, "shape": body.get("shape") if isinstance(body, dict) else None, "representation": body.get("representation") if isinstance(body, dict) else None, "mapping_status": "NOT_VALIDATED", "integrity_status": "NOT_VALIDATED", "semantic_status": "NOT_VALIDATED", "diagnostics": [error.diagnostic()]}


def make_inline_tensor(dtype: str, shape: list[int], values: list[Any], *, tensor_id: str = "ruo:payload:tensor", axes: list[dict[str, Any]] | None = None, validity: dict[str, Any] | None = None, extensions: dict[str, Any] | None = None) -> dict[str, Any]:
    count = shape_product(shape); spec = DTYPES.get(dtype)
    if spec is None: raise TensorError("RUO-T1-003", "Unknown dtype.", stage="dtype")
    stored = [encode_scalar(dtype, value).hex() for value in values] if spec["kind"] in {"float", "bfloat", "complex"} else copy.deepcopy(values)
    body = {"payload_id": tensor_id, "tensor_profile": PROFILE, "dtype": dtype, "rank": len(shape), "shape": shape, "element_count": count, "representation": "inline", "axes": axes or [{"ordinal": index, "size": dimension, "ordering": "ordered", "duplicate_policy": "forbidden", "partial_loading_status": "complete"} for index, dimension in enumerate(shape)], "value_presence": "present", "validity": validity or {"status": "complete", "states": ["valid"] * count}, "storage": {"inline_scalar_encoding": "canonical_hex_bytes" if spec["kind"] in {"float", "bfloat", "complex"} else "canonical_json", "values": stored}, "logical_digest": "", "evidence_refs": [], "extensions": extensions or {}}
    body["logical_digest"] = logical_digest(body)
    return body


def make_dense_tensor(dtype: str, shape: list[int], values: list[Any], *, tensor_id: str = "ruo:payload:tensor", resource_id: str = "ruo:resource:tensor", locator: str = "resources/tensor.ruot", chunk_rows: int | None = None) -> tuple[dict[str, Any], bytes]:
    inline = make_inline_tensor(dtype, shape, values, tensor_id=tensor_id); data = encode_values(dtype, values)
    storage: dict[str, Any] = {"layout": "row_major", "byte_order": "little", "contiguous": True, "offset_bytes": 0, "resource_id": resource_id, "locator": locator, "media_type": MEDIA_TYPE, "byte_size": len(data), "sha256": _sha(data), "chunks": []}
    if data and shape and chunk_rows:
        row_bytes = (shape_product(shape[1:]) if len(shape) > 1 else 1) * DTYPES[dtype]["width"]
        start = 0; index = 0
        while start < shape[0]:
            end = min(shape[0], start + chunk_rows); offset = start * row_bytes; size = (end - start) * row_bytes
            storage["chunks"].append({"index": index, "axis0_start": start, "axis0_end": end, "logical_element_start": offset // DTYPES[dtype]["width"], "logical_element_count": size // DTYPES[dtype]["width"], "byte_offset": offset, "byte_size": size, "sha256": _sha(data[offset:offset + size]), "availability_status": "available"})
            index += 1; start = end
    body = {**inline, "representation": "dense_resource", "storage": storage}
    body["logical_digest"] = logical_digest(body, resource_bytes=data)
    return body, data


def tensor_resource_record(body: dict[str, Any]) -> dict[str, Any]:
    storage = body["storage"]
    return {"resource_id": storage["resource_id"], "owner_payload_id": body.get("payload_id"), "content_sha256": storage["sha256"].removeprefix("sha256:"), "byte_size": storage["byte_size"], "media_type": MEDIA_TYPE, "payload_profile": PAYLOAD_PROFILE, "profile_version": "1", "logical_role": "ruo.role:tensor", "locator_policy": "relative-resource-root", "locator": storage["locator"], "availability_status": "available", "critical": True, "representation": body["representation"], "dtype": body["dtype"], "shape_digest": _sha(canonicalize(body["shape"]).encode()), "chunks": [{**chunk, "sha256": chunk["sha256"].removeprefix("sha256:")} for chunk in storage.get("chunks", [])], "evidence_refs": body.get("evidence_refs", []), "provenance_refs": body.get("evidence_refs", [])}


def resolve_resource(body: dict[str, Any], resource_root: Path) -> bytes:
    locator = body.get("storage", {}).get("locator")
    if not _safe_locator(locator): raise TensorError("RUO-T1-024", "Unsafe Tensor resource locator.", stage="path")
    root = resource_root.resolve(); path = (root / locator).resolve()
    if root != path and root not in path.parents: raise TensorError("RUO-T1-024", "Tensor resource escapes authorized root.", stage="path")
    return path.read_bytes()


def verify_resource(body: dict[str, Any], resource_root: Path) -> dict[str, Any]:
    try: data = resolve_resource(body, resource_root); return validate_tensor(body, resource_bytes=data)
    except (OSError, TensorError) as error:
        diagnostic = error.diagnostic() if isinstance(error, TensorError) else TensorError("RUO-T1-011", str(error), stage="resource").diagnostic()
        return {"ok": False, "tensor_id": body.get("payload_id"), "integrity_status": "NOT_VALIDATED", "semantic_status": "NOT_VALIDATED", "mapping_status": "NOT_VALIDATED", "diagnostics": [diagnostic]}


def convert_tensor(body: dict[str, Any], target: str, *, resource_bytes: bytes | None = None) -> dict[str, Any]:
    values = dense_values(body, resource_bytes=resource_bytes); source_digest = logical_digest(body, resource_bytes=resource_bytes)
    if target == "inline": result = make_inline_tensor(body["dtype"], body["shape"], values, tensor_id=body.get("payload_id", "ruo:payload:tensor"), axes=copy.deepcopy(body["axes"]), validity=copy.deepcopy(body["validity"]), extensions=copy.deepcopy(body.get("extensions", {})))
    elif target == "dense_resource": result, data = make_dense_tensor(body["dtype"], body["shape"], values, tensor_id=body.get("payload_id", "ruo:payload:tensor")); result["axes"] = copy.deepcopy(body["axes"]); result["validity"] = copy.deepcopy(body["validity"]); result["logical_digest"] = logical_digest(result, resource_bytes=data); result["_resource_bytes_hex"] = data.hex()
    elif target == "coo_resource":
        coordinates, sparse_values = [], []
        for index, value in enumerate(values):
            if encode_scalar(body["dtype"], value) != bytes(DTYPES[body["dtype"]]["width"]):
                remainder = index; coordinate = [0] * body["rank"]
                for axis in range(body["rank"] - 1, -1, -1): coordinate[axis] = remainder % body["shape"][axis]; remainder //= body["shape"][axis]
                coordinates.append(coordinate); sparse_values.append(value)
        result = copy.deepcopy(body); result["representation"] = "coo_resource"; result["storage"] = {"nnz": len(coordinates), "index_dtype": "uint64", "coordinates": coordinates, "values": sparse_values, "coordinate_ordering": "lexicographic", "duplicate_coordinate_policy": "forbidden", "explicit_zero_policy": "forbidden"}; result["logical_digest"] = logical_digest(result)
    elif target == "csr_resource":
        if body["rank"] != 2: raise TensorError("RUO-T1-009", "Dense-to-CSR requires rank 2.", stage="conversion")
        pointers, columns, sparse_values = [0], [], []
        for row in range(body["shape"][0]):
            for column in range(body["shape"][1]):
                value = values[row * body["shape"][1] + column]
                if encode_scalar(body["dtype"], value) != bytes(DTYPES[body["dtype"]]["width"]): columns.append(column); sparse_values.append(value)
            pointers.append(len(columns))
        result = copy.deepcopy(body); result["representation"] = "csr_resource"; result["storage"] = {"nnz": len(columns), "row_pointer_dtype": "uint64", "column_index_dtype": "uint64", "row_pointers": pointers, "column_indices": columns, "values": sparse_values, "sorted_columns": True, "duplicate_column_policy": "forbidden", "explicit_zero_policy": "forbidden"}; result["logical_digest"] = logical_digest(result)
    else: raise TensorError("RUO-T1-019", "Unsupported or value-changing canonical conversion.", stage="conversion")
    target_data = bytes.fromhex(result.pop("_resource_bytes_hex")) if "_resource_bytes_hex" in result else None
    target_digest = logical_digest(result, resource_bytes=target_data)
    if target_digest != source_digest: raise TensorError("RUO-T1-019", "Conversion changed logical Tensor semantics.", stage="conversion")
    result["conversion"] = {"profile": "ruo.tensor.conversion/1", "source_logical_digest": source_digest, "target_logical_digest": target_digest, "semantic_loss_count": 0, "identity_loss_count": 0, "mapping_loss_count": 0, "validity_loss_count": 0}
    if target_data is not None: result["resource_bytes_hex"] = target_data.hex()
    return result


def select_tensor(body: dict[str, Any], selector: dict[str, Any], *, resource_bytes: bytes | None = None) -> dict[str, Any]:
    ranges = selector.get("ranges")
    if not isinstance(ranges, list) or len(ranges) != body["rank"]: raise TensorError("RUO-T1-016", "Selector requires one contiguous range per axis.", stage="selection")
    normalized = []
    for dimension, item in zip(body["shape"], ranges):
        if not isinstance(item, list) or len(item) != 2 or any(isinstance(v, bool) or not isinstance(v, int) for v in item) or not 0 <= item[0] <= item[1] <= dimension:
            raise TensorError("RUO-T1-016", "Selector range is invalid.", stage="selection")
        normalized.append(tuple(item))
    source_values = dense_values(body, resource_bytes=resource_bytes); output_values: list[Any] = []
    def visit(axis: int, coordinate: list[int]) -> None:
        if axis == len(normalized): output_values.append(source_values[flat_index(coordinate, body["shape"])]); return
        for value in range(*normalized[axis]): visit(axis + 1, [*coordinate, value])
    visit(0, [])
    axes = copy.deepcopy(body["axes"])
    for axis, (start, end) in zip(axes, normalized):
        axis["size"] = end - start; mapping = axis.get("identity_mapping")
        if isinstance(mapping, dict): mapping["ordered_ids"] = mapping.get("ordered_ids", [])[start:end]; mapping["partial"] = (start, end) != (0, body["shape"][axis["ordinal"]]); mapping["included_positions"] = [[start, end]]; mapping["mapping_digest"] = mapping_digest(body.get("payload_id", ""), axis["ordinal"], mapping)
        axis["partial_loading_status"] = "complete" if (start, end) == (0, body["shape"][axis["ordinal"]]) else "partial"
    result = make_inline_tensor(body["dtype"], [end - start for start, end in normalized], output_values, tensor_id=body.get("payload_id", "ruo:payload:tensor") + ":selection", axes=axes, validity={"status": "partial", "states": ["valid"] * len(output_values)})
    result["selection"] = {"source_tensor_id": body.get("payload_id"), "source_logical_digest": logical_digest(body, resource_bytes=resource_bytes), "slice_ranges": [list(item) for item in normalized], "included_chunks": [], "not_loaded_regions": [list(item) for item in normalized if item != (0, body["shape"][len(normalized) - len(normalized)])]}
    return result


def atomic_publish(resource: bytes, body: dict[str, Any], resource_path: Path, metadata_path: Path) -> dict[str, Any]:
    validation = validate_tensor(body, resource_bytes=resource)
    if not validation["ok"]: raise TensorError("RUO-T1-021", "Refusing to publish an invalid Tensor.", stage="publication", metadata={"diagnostics": validation["diagnostics"]})
    resource_path.parent.mkdir(parents=True, exist_ok=True); metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_paths: list[Path] = []
    try:
        for target, data in ((resource_path, resource), (metadata_path, (json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode())):
            fd, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent); os.close(fd); temporary = Path(name); temporary.write_bytes(data); temporary_paths.append(temporary)
        if _sha(temporary_paths[0].read_bytes()) != _sha(resource): raise TensorError("RUO-T1-021", "Temporary resource verification failed.", stage="publication")
        os.replace(temporary_paths[0], resource_path); temporary_paths.pop(0)
        os.replace(temporary_paths[0], metadata_path); temporary_paths.pop(0)
        return {"ok": True, "resource_sha256": _sha(resource), "logical_digest": validation["logical_digest"], "rollback_required": False}
    finally:
        for path in temporary_paths:
            try: path.unlink()
            except FileNotFoundError: pass
