"""MIRP-T1 canonical local exchange messages for ReasonGraph fragments."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .mirp_projection import MIRP_GRAPH_FRAGMENT_SCHEMA, project_mirp_fragment
from .model import canonicalize_graph, graph_hash, validate_graph


FORMAT_VERSION = "1.0"
MEDIA_TYPE = "application/vnd.reasonscript.mirp-graph-fragment+jsonl"
PROFILE = "mra-mirp-transport/0.1"
MAGIC = "MIRP-T1"


class MIRPTransportError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def encode_fragment(fragment: dict[str, Any]) -> bytes:
    _validate_fragment(fragment)
    graph = fragment["graph"]
    header = {"magic": MAGIC, "format_version": FORMAT_VERSION, "media_type": MEDIA_TYPE, "profile": PROFILE, "graph_id": graph["graph_id"], "fragment_hash": fragment["fragment_hash"]}
    records = [_envelope("message_header", header, 0), _envelope("graph_fragment", fragment, 1)]
    content = b"".join(_line(record) for record in records)
    seal = {"format_version": FORMAT_VERSION, "graph_id": graph["graph_id"], "fragment_hash": fragment["fragment_hash"], "content_stream_sha256": _sha(content), "content_record_count": 2, "total_record_count": 3}
    return content + _line(_envelope("message_seal", seal, 2))


def decode_fragment(payload: bytes) -> dict[str, Any]:
    if not payload.endswith(b"\n") or b"\r" in payload or b"\x00" in payload:
        raise MIRPTransportError("MIRP-T1-001", "MIRP-T1 requires canonical LF-delimited UTF-8 records.")
    lines = payload[:-1].split(b"\n")
    if len(lines) != 3 or any(not line for line in lines):
        raise MIRPTransportError("MIRP-T1-002", "MIRP-T1 requires header, graph fragment, and seal records.")
    records = [_parse(line, ordinal) for ordinal, line in enumerate(lines)]
    if [record["record_type"] for record in records] != ["message_header", "graph_fragment", "message_seal"]:
        raise MIRPTransportError("MIRP-T1-002", "MIRP-T1 record order is invalid.")
    header, fragment, seal = (record["body"] for record in records)
    expected = {"magic": MAGIC, "format_version": FORMAT_VERSION, "media_type": MEDIA_TYPE, "profile": PROFILE}
    if any(header.get(key) != value for key, value in expected.items()):
        raise MIRPTransportError("MIRP-T1-003", "MIRP-T1 header is incompatible.")
    _validate_fragment(fragment)
    if header.get("graph_id") != fragment["graph"]["graph_id"] or header.get("fragment_hash") != fragment["fragment_hash"] or seal.get("graph_id") != fragment["graph"]["graph_id"] or seal.get("fragment_hash") != fragment["fragment_hash"]:
        raise MIRPTransportError("MIRP-T1-003", "MIRP-T1 identities are inconsistent.")
    content = b"".join(line + b"\n" for line in lines[:2])
    if seal.get("content_record_count") != 2 or seal.get("total_record_count") != 3 or not hmac.compare_digest(str(seal.get("content_stream_sha256", "")), _sha(content)):
        raise MIRPTransportError("MIRP-T1-004", "MIRP-T1 content seal is invalid.")
    return fragment


def export_graph(graph: dict[str, Any], target: Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Create and atomically publish a complete-graph MIRP message."""
    if target.suffix != ".mirp":
        raise MIRPTransportError("MIRP-T1-005", "MIRP-T1 files must use the .mirp extension.")
    if target.exists() and not overwrite:
        raise MIRPTransportError("MIRP-T1-006", "Existing MIRP-T1 target requires overwrite=True.")
    fragment = project_mirp_fragment(graph)
    payload = encode_fragment(fragment)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".mirp-", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name); handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target); temporary = None
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()
    return {"path": str(target), "bytes": len(payload), "sha256": _sha(payload), "graph_hash": graph_hash(graph), "fragment_hash": fragment["fragment_hash"]}


def read_message(path: Path) -> dict[str, Any]:
    if path.suffix != ".mirp":
        raise MIRPTransportError("MIRP-T1-005", "MIRP-T1 files must use the .mirp extension.")
    return decode_fragment(path.read_bytes())


def _validate_fragment(fragment: Any) -> None:
    if not isinstance(fragment, dict) or set(fragment) != {"schema", "fragment_kind", "graph", "fragment_hash"} or fragment.get("schema") != MIRP_GRAPH_FRAGMENT_SCHEMA:
        raise MIRPTransportError("MIRP-T1-007", "MIRP graph fragment is invalid.")
    if validate_graph(fragment["graph"]):
        raise MIRPTransportError("MIRP-T1-007", "MIRP graph fragment contains an invalid ReasonGraph.")
    expected = "sha256:" + hashlib.sha256(canonicalize_graph({key: fragment[key] for key in ("schema", "fragment_kind", "graph")}).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(str(fragment.get("fragment_hash", "")), expected):
        raise MIRPTransportError("MIRP-T1-007", "MIRP graph fragment hash is invalid.")


def _envelope(record_type: str, body: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {"record_type": record_type, "record_version": FORMAT_VERSION, "ordinal": ordinal, "body": body, "body_sha256": _sha(_canonical_bytes(body))}


def _line(record: dict[str, Any]) -> bytes:
    return _canonical_bytes(record) + b"\n"


def _parse(line: bytes, ordinal: int) -> dict[str, Any]:
    try:
        value = json.loads(line.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise MIRPTransportError("MIRP-T1-001", f"Invalid MIRP-T1 JSON record: {error}") from error
    if not isinstance(value, dict) or set(value) != {"record_type", "record_version", "ordinal", "body", "body_sha256"} or value.get("record_version") != FORMAT_VERSION or value.get("ordinal") != ordinal or not isinstance(value.get("body"), dict) or _canonical_bytes(value) != line:
        raise MIRPTransportError("MIRP-T1-002", "MIRP-T1 record envelope is invalid.")
    if not hmac.compare_digest(str(value["body_sha256"]), _sha(_canonical_bytes(value["body"]))):
        raise MIRPTransportError("MIRP-T1-004", "MIRP-T1 record body digest is invalid.")
    return value


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result: raise MIRPTransportError("MIRP-T1-001", "Duplicate MIRP-T1 JSON key.")
        result[key] = value
    return result


def _canonical_bytes(value: Any) -> bytes:
    return canonicalize_graph(value).encode("utf-8")


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
