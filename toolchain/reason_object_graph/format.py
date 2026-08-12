"""RGO-F1 canonical JSON Lines persistence for ReasonGraph v0.1."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .model import canonicalize_graph, graph_hash, validate_graph


FORMAT_VERSION = "1.0"
MEDIA_TYPE = "application/vnd.reasonscript.reason-graph+jsonl"
CANONICALIZATION_PROFILE = "reason-object-graph-canonical-jsonl/1"
LOGICAL_MODEL = "mra-reason-object-graph/0.1"
MAGIC = "REASONGRAPH-F1"


class ReasonGraphFileError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def encode_graph(graph: dict[str, Any]) -> bytes:
    diagnostics = validate_graph(graph)
    if diagnostics:
        raise ReasonGraphFileError("RGO-F1-001", f"Cannot encode invalid ReasonGraph: {diagnostics[0]['code']}")
    header = {
        "magic": MAGIC,
        "format_version": FORMAT_VERSION,
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "logical_model": LOGICAL_MODEL,
        "media_type": MEDIA_TYPE,
        "graph_id": graph["graph_id"],
    }
    records = [_envelope("file_header", header, 0), _envelope("graph", graph, 1)]
    content = b"".join(_line(record) for record in records)
    seal = {
        "format_version": FORMAT_VERSION,
        "graph_id": graph["graph_id"],
        "graph_hash": graph_hash(graph),
        "content_stream_sha256": _sha(content),
        "content_record_count": len(records),
        "total_record_count": len(records) + 1,
    }
    return content + _line(_envelope("file_seal", seal, 2))


def decode_graph(payload: bytes) -> dict[str, Any]:
    if not payload.endswith(b"\n") or b"\r" in payload or b"\x00" in payload:
        raise ReasonGraphFileError("RGO-F1-002", "RGO-F1 requires LF-delimited canonical UTF-8 records.")
    lines = payload[:-1].split(b"\n")
    if len(lines) != 3 or any(not line for line in lines):
        raise ReasonGraphFileError("RGO-F1-003", "RGO-F1 requires exactly header, graph, and seal records.")
    records = [_parse(line, ordinal) for ordinal, line in enumerate(lines)]
    if [record["record_type"] for record in records] != ["file_header", "graph", "file_seal"]:
        raise ReasonGraphFileError("RGO-F1-003", "RGO-F1 record order is invalid.")
    header, graph, seal = (record["body"] for record in records)
    expected_header = {
        "magic": MAGIC,
        "format_version": FORMAT_VERSION,
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "logical_model": LOGICAL_MODEL,
        "media_type": MEDIA_TYPE,
    }
    if any(header.get(key) != value for key, value in expected_header.items()):
        raise ReasonGraphFileError("RGO-F1-004", "RGO-F1 header is incompatible.")
    if header.get("graph_id") != graph.get("graph_id") or seal.get("graph_id") != graph.get("graph_id"):
        raise ReasonGraphFileError("RGO-F1-004", "RGO-F1 graph identity is inconsistent.")
    content = b"".join(line + b"\n" for line in lines[:2])
    if seal.get("content_record_count") != 2 or seal.get("total_record_count") != 3 or not hmac.compare_digest(str(seal.get("content_stream_sha256", "")), _sha(content)):
        raise ReasonGraphFileError("RGO-F1-005", "RGO-F1 content seal is invalid.")
    if not hmac.compare_digest(str(seal.get("graph_hash", "")), graph_hash(graph)):
        raise ReasonGraphFileError("RGO-F1-006", "RGO-F1 graph hash is invalid.")
    diagnostics = validate_graph(graph)
    if diagnostics:
        raise ReasonGraphFileError("RGO-F1-007", f"Decoded ReasonGraph is invalid: {diagnostics[0]['code']}")
    return graph


def write_graph(graph: dict[str, Any], target: Path, *, overwrite: bool = False) -> dict[str, Any]:
    if target.suffix != ".rgraph":
        raise ReasonGraphFileError("RGO-F1-008", "RGO-F1 files must use the .rgraph extension.")
    if target.exists() and not overwrite:
        raise ReasonGraphFileError("RGO-F1-009", "Existing RGO-F1 target requires overwrite=True.")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = encode_graph(graph)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".rgraph-", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target); temporary = None
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()
    return {"path": str(target), "bytes": len(payload), "sha256": _sha(payload), "graph_hash": graph_hash(graph)}


def read_graph(path: Path) -> dict[str, Any]:
    if path.suffix != ".rgraph":
        raise ReasonGraphFileError("RGO-F1-008", "RGO-F1 files must use the .rgraph extension.")
    return decode_graph(path.read_bytes())


def validate_graph_file(path: Path) -> dict[str, Any]:
    try:
        graph = read_graph(path)
        return {"ok": True, "graph_id": graph["graph_id"], "graph_hash": graph_hash(graph), "diagnostics": []}
    except (OSError, ReasonGraphFileError) as error:
        code = error.code if isinstance(error, ReasonGraphFileError) else "RGO-F1-002"
        return {"ok": False, "diagnostics": [{"code": code, "message": str(error)}]}


def _envelope(record_type: str, body: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {"record_type": record_type, "record_version": FORMAT_VERSION, "ordinal": ordinal, "body": body, "body_sha256": _sha(_canonical_bytes(body))}


def _line(record: dict[str, Any]) -> bytes:
    return _canonical_bytes(record) + b"\n"


def _parse(line: bytes, ordinal: int) -> dict[str, Any]:
    try:
        value = json.loads(line.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise ReasonGraphFileError("RGO-F1-002", f"Invalid RGO-F1 JSON record: {error}") from error
    if not isinstance(value, dict) or set(value) != {"record_type", "record_version", "ordinal", "body", "body_sha256"} or value.get("record_version") != FORMAT_VERSION or value.get("ordinal") != ordinal or not isinstance(value.get("body"), dict):
        raise ReasonGraphFileError("RGO-F1-003", "RGO-F1 record envelope is invalid.")
    if _canonical_bytes(value) != line:
        raise ReasonGraphFileError("RGO-F1-002", "RGO-F1 record is not canonical JSON.")
    if not hmac.compare_digest(str(value["body_sha256"]), _sha(_canonical_bytes(value["body"]))):
        raise ReasonGraphFileError("RGO-F1-005", "RGO-F1 record body digest is invalid.")
    return value


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result: raise ReasonGraphFileError("RGO-F1-002", "Duplicate RGO-F1 JSON key.")
        result[key] = value
    return result


def _canonical_bytes(value: Any) -> bytes:
    return canonicalize_graph(value).encode("utf-8")


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
