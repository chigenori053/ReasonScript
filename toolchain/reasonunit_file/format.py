"""Strict RUO-F1 JSON Lines reader, writer, selector, and resource verifier."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import math
import os
import re
import tempfile
import unicodedata
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from toolchain.reasonunit_object.model import canonical_digest, validate_object

FORMAT_VERSION = "1.0"
MEDIA_TYPE = "application/vnd.reasonscript.ruo+jsonl"
CANONICALIZATION_PROFILE = "ruo-canonical-jsonl/1"
LOGICAL_MODEL = "ruo-u1/1.0"
SECTION_ORDER = (
    "file_header", "section_manifest", "object", "unit", "payload", "state",
    "relation", "constraint", "evidence", "dependency", "revision",
    "transaction_summary", "extension", "projection_descriptor",
    "external_resource", "file_seal",
)
CONTENT_SECTIONS = SECTION_ORDER[2:-1]
ID_KEYS = {
    "unit": "entity_id", "payload": "payload_id", "state": "state_id",
    "relation": "relation_id", "constraint": "constraint_id",
    "evidence": "evidence_id", "dependency": "source_id", "revision": "revision_id",
    "transaction_summary": "transaction_id", "extension": "namespace",
    "projection_descriptor": "projection_id", "external_resource": "resource_id",
}
DEFAULT_LIMITS = {
    "file_bytes": 16_000_000, "record_bytes": 2_000_000, "record_count": 100_000,
    "section_count": 16, "nesting_depth": 128, "string_bytes": 2_000_000,
    "members": 100_000, "external_resources": 10_000, "external_bytes": 1 << 40,
    "chunks": 100_000, "selector_expansion": 100_000, "diagnostics": 1_000,
}


class RUOFileError(ValueError):
    def __init__(self, code: str, message: str, *, stage: str = "file", ordinal: int | None = None, record_type: str | None = None, metadata: dict[str, Any] | None = None):
        super().__init__(message); self.code = code; self.stage = stage; self.ordinal = ordinal; self.record_type = record_type; self.metadata = metadata or {}

    def diagnostic(self) -> dict[str, Any]:
        return {"code": self.code, "severity": "ERROR", "stage": self.stage, "record_ordinal": self.ordinal, "record_type": self.record_type, "affected_ids": [], "metadata": self.metadata, "message": str(self)}


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _depth(value: Any) -> int:
    if isinstance(value, dict): return 1 + max((_depth(item) for item in value.values()), default=0)
    if isinstance(value, list): return 1 + max((_depth(item) for item in value), default=0)
    return 0


def _validate_strings(value: Any) -> None:
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value: raise RUOFileError("RUO-F1-005", "Strings and keys must already be NFC.", stage="canonical_json")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value): raise RUOFileError("RUO-F1-005", "Unpaired Unicode surrogate is prohibited.", stage="canonical_json")
    elif isinstance(value, dict):
        for key, child in value.items(): _validate_strings(key); _validate_strings(child)
    elif isinstance(value, list):
        for child in value: _validate_strings(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise RUOFileError("RUO-F1-005", "NaN and infinity are prohibited.", stage="canonical_json")


def _normalize_numbers(value: Any) -> Any:
    if isinstance(value, float) and value == 0: return 0
    if isinstance(value, dict): return {key: _normalize_numbers(child) for key, child in value.items()}
    if isinstance(value, list): return [_normalize_numbers(child) for child in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    _validate_strings(value)
    try: return json.dumps(_normalize_numbers(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error: raise RUOFileError("RUO-F1-005", f"Value is not canonical JSON: {error}", stage="canonical_json") from error


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result: raise RUOFileError("RUO-F1-004", f"Duplicate JSON key: {key}", stage="json")
        result[key] = value
    return result


def _parse_line(line: bytes, ordinal: int, limits: dict[str, int]) -> dict[str, Any]:
    if len(line) > limits["record_bytes"]: raise RUOFileError("RUO-F1-024", "Record byte limit exceeded.", stage="limits", ordinal=ordinal)
    try: text = line.decode("utf-8")
    except UnicodeDecodeError as error: raise RUOFileError("RUO-F1-003", "Invalid UTF-8.", stage="physical", ordinal=ordinal) from error
    try: value = json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda token: (_ for _ in ()).throw(RUOFileError("RUO-F1-005", f"Invalid number: {token}", stage="canonical_json", ordinal=ordinal)))
    except RUOFileError: raise
    except json.JSONDecodeError as error: raise RUOFileError("RUO-F1-004", f"Invalid JSON: {error.msg}", stage="json", ordinal=ordinal) from error
    if not isinstance(value, dict): raise RUOFileError("RUO-F1-004", "Every record must be a JSON object.", stage="json", ordinal=ordinal)
    _validate_strings(value)
    if _depth(value) > limits["nesting_depth"]: raise RUOFileError("RUO-F1-024", "JSON nesting limit exceeded.", stage="limits", ordinal=ordinal)
    if canonical_json_bytes(value) != line: raise RUOFileError("RUO-F1-005", "Record is not canonical JSON.", stage="canonical_json", ordinal=ordinal)
    return value


def _envelope(record_type: str, body: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {"body": body, "body_sha256": _sha(canonical_json_bytes(body)), "ordinal": ordinal, "record_type": record_type, "record_version": "1.0"}


def _line(record: dict[str, Any]) -> bytes:
    return canonical_json_bytes(record) + b"\n"


def _logical_sections(value: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    excluded = {"units", "payloads", "states", "relations", "constraints", "evidence_registry", "dependency_graph", "revisions", "extension_registry", "projection_descriptors"}
    for optional in ("transaction_summaries", "external_resources"):
        if value.get(optional): excluded.add(optional)
    sections = {name: [] for name in CONTENT_SECTIONS}
    sections["object"] = [{key: copy.deepcopy(child) for key, child in value.items() if key not in excluded}]
    mapping = {"unit": "units", "payload": "payloads", "state": "states", "relation": "relations", "constraint": "constraints", "evidence": "evidence_registry", "dependency": "dependency_graph", "revision": "revisions", "transaction_summary": "transaction_summaries", "extension": "extension_registry", "projection_descriptor": "projection_descriptors", "external_resource": "external_resources"}
    for section, logical_key in mapping.items(): sections[section] = copy.deepcopy(value.get(logical_key, []))
    for section, records in sections.items():
        if section == "object": continue
        key = ID_KEYS[section]
        secondary = "target_id" if section == "dependency" else key
        records.sort(key=lambda item: (str(item.get(key, "")), str(item.get(secondary, ""))))
    return sections


def _header(value: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    return {"canonicalization_profile": CANONICALIZATION_PROFILE, "extension_namespaces": sorted(str(item.get("namespace")) for item in value.get("extension_registry", [])), "external_resource_policy": "offline-explicit-root", "format_version": FORMAT_VERSION, "logical_model": LOGICAL_MODEL, "magic": "REASONSCRIPT-RUO", "media_type": MEDIA_TYPE, "object_id": value["object_identity"]["entity_id"], "object_revision_id": value["current_revision"], "object_schema_version": value.get("model_version", "reasonscript-reasonunit-object/1.0"), "partial_file": partial, "payload_profile_ids": sorted({str(item.get("profile_id")) for item in value.get("payloads", [])})}


def encode_file(value: dict[str, Any], *, partial: bool = False) -> bytes:
    _validate_strings(value)
    sections = _logical_sections(value)
    counts = {name: len(sections.get(name, [])) for name in CONTENT_SECTIONS}
    counts.update({"file_header": 1, "section_manifest": 1, "file_seal": 1})
    # Header and manifest are fixed at ordinals 0 and 1; the seal follows all content.
    next_ordinal = 2; descriptors = []
    for section in SECTION_ORDER:
        count = counts[section]
        if section == "file_header": first = last = 0
        elif section == "section_manifest": first = last = 1
        elif section == "file_seal": first = last = 2 + sum(counts[name] for name in CONTENT_SECTIONS)
        else:
            first = next_ordinal if count else None; last = next_ordinal + count - 1 if count else None; next_ordinal += count
        descriptors.append({"critical": section not in {"transaction_summary", "extension", "projection_descriptor", "external_resource"}, "first_ordinal": first, "last_ordinal": last, "partial_loading_status": "included" if count else ("not_loaded" if partial else "empty"), "record_count": count, "record_type": section, "required": section in {"file_header", "section_manifest", "object", "file_seal"}, "schema_version": "1.0", "section": section, "stable_sort_key": ID_KEYS.get(section, "ordinal" if section != "object" else "object_id")})
    records = [_envelope("file_header", _header(value, partial=partial), 0), _envelope("section_manifest", {"sections": descriptors}, 1)]
    for section in CONTENT_SECTIONS:
        for body in sections[section]: records.append(_envelope(section, body, len(records)))
    record_lines = [_line(record) for record in records]
    section_digests = []
    for section in SECTION_ORDER[:-1]:
        selected = b"".join(line for record, line in zip(records, record_lines) if record["record_type"] == section)
        section_digests.append({"record_count": sum(record["record_type"] == section for record in records), "section": section, "sha256": _sha(selected)})
    external_bytes = b"".join(line for record, line in zip(records, record_lines) if record["record_type"] == "external_resource")
    seal_body = {"content_record_count": len(records), "content_stream_sha256": _sha(b"".join(record_lines)), "external_resource_manifest_sha256": _sha(external_bytes), "format_version": FORMAT_VERSION, "logical_object_digest": canonical_digest(value), "object_id": value["object_identity"]["entity_id"], "object_revision_id": value["current_revision"], "seal_algorithm_version": "ruo-seal/1", "section_digests": section_digests, "total_record_count": len(records) + 1}
    return b"".join(record_lines) + _line(_envelope("file_seal", seal_body, len(records)))


def _decode(data: bytes, *, mode: str = "strict", limits: dict[str, int] | None = None) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    limits = {**DEFAULT_LIMITS, **(limits or {})}
    if mode not in {"strict", "preserve", "inspect"}: raise RUOFileError("RUO-F1-023", "Unknown reader compatibility mode.", stage="compatibility")
    if len(data) > limits["file_bytes"]: raise RUOFileError("RUO-F1-024", "File byte limit exceeded.", stage="limits")
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or b"\x00" in data or not data.endswith(b"\n"):
        raise RUOFileError("RUO-F1-003", "BOM, CR, NUL, or missing final LF is prohibited.", stage="physical")
    raw_lines = data[:-1].split(b"\n")
    if any(not line for line in raw_lines): raise RUOFileError("RUO-F1-003", "Blank records are prohibited.", stage="physical")
    if len(raw_lines) > limits["record_count"]: raise RUOFileError("RUO-F1-024", "Record count limit exceeded.", stage="limits")
    records = [_parse_line(line, ordinal, limits) for ordinal, line in enumerate(raw_lines)]
    for ordinal, record in enumerate(records):
        record_type = record.get("record_type")
        if set(record) != {"body", "body_sha256", "ordinal", "record_type", "record_version"} or record.get("ordinal") != ordinal or record.get("record_version") != "1.0":
            raise RUOFileError("RUO-F1-006", "Invalid record envelope, ordinal, or version.", stage="record", ordinal=ordinal, record_type=str(record_type))
        expected = _sha(canonical_json_bytes(record["body"])); observed = record.get("body_sha256", "")
        if not hmac.compare_digest(expected, str(observed)): raise RUOFileError("RUO-F1-007", "Record body digest mismatch.", stage="integrity", ordinal=ordinal, record_type=str(record_type), metadata={"expected": expected, "observed": observed})
    if records[0].get("record_type") != "file_header" or records[1].get("record_type") != "section_manifest": raise RUOFileError("RUO-F1-006", "Header and section manifest must be first.", stage="record")
    if records[-1].get("record_type") != "file_seal" or sum(record.get("record_type") == "file_seal" for record in records) != 1: raise RUOFileError("RUO-F1-014", "Exactly one final seal is required.", stage="seal")
    order = [SECTION_ORDER.index(str(record.get("record_type"))) if record.get("record_type") in SECTION_ORDER else -1 for record in records]
    if -1 in order:
        unknown = records[order.index(-1)]
        raise RUOFileError("RUO-F1-006", "Unknown record type.", stage="record", ordinal=unknown["ordinal"], record_type=str(unknown["record_type"]))
    if order != sorted(order): raise RUOFileError("RUO-F1-006", "Record sections are out of order.", stage="record")
    header = records[0]["body"]
    required_header = {"magic": "REASONSCRIPT-RUO", "format_version": FORMAT_VERSION, "canonicalization_profile": CANONICALIZATION_PROFILE, "logical_model": LOGICAL_MODEL, "media_type": MEDIA_TYPE}
    if any(header.get(key) != expected for key, expected in required_header.items()): raise RUOFileError("RUO-F1-008", "Header format or logical-model mismatch.", stage="header")
    descriptors = records[1]["body"].get("sections", [])
    if len(descriptors) != len(SECTION_ORDER): raise RUOFileError("RUO-F1-009", "Section manifest is incomplete.", stage="manifest")
    for descriptor, section in zip(descriptors, SECTION_ORDER):
        actual = [record for record in records if record["record_type"] == section]
        ordinals = [record["ordinal"] for record in actual]
        expected_range = (ordinals[0], ordinals[-1]) if ordinals else (None, None)
        if descriptor.get("section") != section or descriptor.get("record_count") != len(actual) or (descriptor.get("first_ordinal"), descriptor.get("last_ordinal")) != expected_range:
            raise RUOFileError("RUO-F1-009", "Section count or ordinal range mismatch.", stage="manifest", record_type=section)
        key = ID_KEYS.get(section)
        if key and section != "dependency":
            ids = [str(record["body"].get(key, "")) for record in actual]
            if ids != sorted(ids) or len(ids) != len(set(ids)): raise RUOFileError("RUO-F1-010", "Entity records must be unique and sorted.", stage="entity", record_type=section)
    if sum(record["record_type"] == "object" for record in records) != 1: raise RUOFileError("RUO-F1-010", "Exactly one Object record is required.", stage="entity", record_type="object")
    seal = records[-1]["body"]; before_seal = raw_lines[:-1]
    content_bytes = b"".join(line + b"\n" for line in before_seal)
    if seal.get("total_record_count") != len(records) or seal.get("content_record_count") != len(records) - 1 or not hmac.compare_digest(str(seal.get("content_stream_sha256", "")), _sha(content_bytes)):
        raise RUOFileError("RUO-F1-015", "Content-stream digest or record count mismatch.", stage="seal")
    declared_sections = {item.get("section"): item for item in seal.get("section_digests", [])}
    for section in SECTION_ORDER[:-1]:
        section_bytes = b"".join(raw_lines[index] + b"\n" for index, record in enumerate(records[:-1]) if record["record_type"] == section)
        entry = declared_sections.get(section, {})
        if entry.get("record_count") != sum(record["record_type"] == section for record in records[:-1]) or not hmac.compare_digest(str(entry.get("sha256", "")), _sha(section_bytes)):
            raise RUOFileError("RUO-F1-015", "Section digest mismatch.", stage="seal", record_type=section)
    external_bytes = b"".join(raw_lines[index] + b"\n" for index, record in enumerate(records[:-1]) if record["record_type"] == "external_resource")
    if not hmac.compare_digest(str(seal.get("external_resource_manifest_sha256", "")), _sha(external_bytes)): raise RUOFileError("RUO-F1-015", "External-resource manifest digest mismatch.", stage="seal")
    logical = copy.deepcopy(next(record["body"] for record in records if record["record_type"] == "object"))
    mapping = {"unit": "units", "payload": "payloads", "state": "states", "relation": "relations", "constraint": "constraints", "evidence": "evidence_registry", "dependency": "dependency_graph", "revision": "revisions", "transaction_summary": "transaction_summaries", "extension": "extension_registry", "projection_descriptor": "projection_descriptors", "external_resource": "external_resources"}
    for section, logical_key in mapping.items():
        bodies = [copy.deepcopy(record["body"]) for record in records if record["record_type"] == section]
        if bodies or logical_key not in {"transaction_summaries", "external_resources"}:
            logical[logical_key] = bodies
    if header.get("object_id") != logical.get("object_identity", {}).get("entity_id") or header.get("object_revision_id") != logical.get("current_revision"):
        raise RUOFileError("RUO-F1-008", "Header Object identity or revision is stale.", stage="header")
    if bool(header.get("partial_file")) != bool(logical.get("partial_loading", {}).get("is_partial")):
        raise RUOFileError("RUO-F1-017", "Header and logical partial-file declarations disagree.", stage="partial")
    for extension in logical.get("extension_registry", []):
        if extension.get("critical") and not extension.get("understood", False):
            raise RUOFileError("RUO-F1-013", "Unknown critical extension cannot be materialized.", stage="extension", metadata={"namespace": extension.get("namespace")})
        if extension.get("overrides_core"):
            raise RUOFileError("RUO-F1-013", "Extension cannot override core invariants.", stage="extension", metadata={"namespace": extension.get("namespace")})
    resources = logical.get("external_resources", [])
    if len(resources) > limits["external_resources"] or sum(int(item.get("byte_size", 0)) for item in resources) > limits["external_bytes"]:
        raise RUOFileError("RUO-F1-024", "External resource limit exceeded.", stage="limits")
    for resource in resources:
        locator = str(resource.get("locator", "")); chunks = resource.get("chunks", [])
        if not _safe_locator(locator): raise RUOFileError("RUO-F1-025", "Unsafe external resource locator.", stage="path", metadata={"resource_id": resource.get("resource_id")})
        if len(chunks) > limits["chunks"]: raise RUOFileError("RUO-F1-024", "Chunk count limit exceeded.", stage="limits")
        offset = 0
        for index, chunk in enumerate(chunks):
            size = chunk.get("byte_size")
            if chunk.get("index") != index or chunk.get("byte_offset") != offset or not isinstance(size, int) or size < 0:
                raise RUOFileError("RUO-F1-012", "Malformed chunk coverage.", stage="resource", metadata={"resource_id": resource.get("resource_id")})
            offset += size
        if chunks and offset != resource.get("byte_size"): raise RUOFileError("RUO-F1-012", "Chunk coverage does not match resource byte size.", stage="resource", metadata={"resource_id": resource.get("resource_id")})
    if canonical_digest(logical) != seal.get("logical_object_digest"): raise RUOFileError("RUO-F1-016", "Logical Object digest mismatch.", stage="semantic")
    semantic_diagnostics = [] if header.get("partial_file") else validate_object(logical)
    if semantic_diagnostics and mode != "inspect": raise RUOFileError("RUO-F1-021", "Decoded Object fails RUO-U1 semantic validation.", stage="semantic", metadata={"diagnostics": semantic_diagnostics[:10]})
    statuses = {"complete_object_semantic_status": "NOT_EVALUATED" if mode == "inspect" else ("INDETERMINATE" if header.get("partial_file") else "VALID"), "external_resource_status": "NOT_VERIFIED", "physical_integrity_status": "VALID", "selected_record_schema_status": "VALID", "selected_view_semantic_status": "NOT_EVALUATED" if mode == "inspect" else "VALID"}
    return (None if mode == "inspect" else logical), records, {"header": header, "seal": seal, "statuses": statuses}


def validate_file(path: Path, *, mode: str = "strict", limits: dict[str, int] | None = None) -> dict[str, Any]:
    try:
        if path.suffix != ".ruo": raise RUOFileError("RUO-F1-002", "Canonical file extension must be lowercase .ruo.", stage="identity")
        logical, records, metadata = _decode(path.read_bytes(), mode=mode, limits=limits)
        return {"ok": True, "format_version": FORMAT_VERSION, "object_id": metadata["header"]["object_id"], "object_revision_id": metadata["header"]["object_revision_id"], "record_count": len(records), "digests": {"content_stream_sha256": metadata["seal"]["content_stream_sha256"], "logical_object_digest": metadata["seal"]["logical_object_digest"]}, "semantic_status": metadata["statuses"]["complete_object_semantic_status"], "validation_stages": metadata["statuses"], "diagnostics": []}
    except (OSError, RUOFileError) as error:
        diagnostic = error.diagnostic() if isinstance(error, RUOFileError) else RUOFileError("RUO-F1-003", str(error), stage="physical").diagnostic()
        return {"ok": False, "format_version": FORMAT_VERSION, "semantic_status": "NOT_VALIDATED", "validation_stages": {}, "diagnostics": [diagnostic]}


def read_file(path: Path, *, mode: str = "strict", limits: dict[str, int] | None = None) -> dict[str, Any]:
    data = path.read_bytes(); logical, _, _ = _decode(data, mode=mode, limits=limits)
    if logical is None: raise RUOFileError("RUO-F1-018", "Inspect mode never constructs a semantic Object.", stage="reader")
    return logical


def inspect_file(path: Path, *, limits: dict[str, int] | None = None) -> dict[str, Any]:
    result = validate_file(path, mode="inspect", limits=limits); result["mode"] = "inspect"; result["semantic_status"] = "NOT_EVALUATED"; return result


def write_file(value: dict[str, Any], target: Path, *, overwrite: bool = False, expected_digest: str | None = None, partial: bool = False) -> dict[str, Any]:
    if target.suffix != ".ruo": raise RUOFileError("RUO-F1-002", "Writer output must use lowercase .ruo.", stage="writer")
    if not partial:
        diagnostics = validate_object(value)
        if diagnostics: raise RUOFileError("RUO-F1-021", "Writer accepts only a valid RUO-U1 Object.", stage="writer", metadata={"diagnostics": diagnostics[:10]})
    if target.exists() and not overwrite and expected_digest is None: raise RUOFileError("RUO-F1-020", "Existing target requires --overwrite or expected digest.", stage="writer")
    if target.exists() and expected_digest is not None and _sha(target.read_bytes()) != expected_digest: raise RUOFileError("RUO-F1-020", "Existing target digest does not match expected digest.", stage="writer")
    payload = encode_file(value, partial=partial); target.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".ruo-write-", suffix=".tmp", dir=target.parent, delete=False) as handle:
            temp_name = handle.name; handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        temporary = Path(temp_name)
        # Verification before publication; suffix is deliberately temporary so decode directly.
        _decode(temporary.read_bytes(), mode="strict")
        os.replace(temporary, target); temp_name = None
    finally:
        if temp_name:
            try: Path(temp_name).unlink()
            except OSError: pass
    verified = validate_file(target)
    if not verified["ok"]: raise RUOFileError("RUO-F1-020", "Published file did not reopen and verify.", stage="writer")
    return {"path": str(target), "bytes": len(payload), "sha256": _sha(payload), **verified}


def _selected_ids(value: dict[str, Any], selector: dict[str, Any]) -> set[str]:
    selected = set(map(str, selector.get("entity_ids", [])))
    kinds = set(map(str, selector.get("entity_kinds", []))); profiles = set(map(str, selector.get("payload_profiles", []))); roles = set(map(str, selector.get("semantic_roles", [])))
    if kinds:
        selected.update(str(unit["entity_id"]) for unit in value.get("units", []) if unit.get("entity_kind") in kinds)
    selected.update(str(payload["payload_id"]) for payload in value.get("payloads", []) if (profiles and payload.get("profile_id") in profiles) or (roles and payload.get("semantic_role") in roles))
    for root in selector.get("containment_roots", []):
        selected.add(str(root)); pending = [str(root)]; depth = int(selector.get("containment_depth", 1 << 20)); current = 0
        units = {unit["entity_id"]: unit for unit in value.get("units", [])}
        while pending and current < depth:
            children = [str(child) for node in pending for child in units.get(node, {}).get("children", [])]; selected.update(children); pending = children; current += 1
    if selector.get("include_evidence_closure"):
        refs = set()
        for registry in (value.get("payloads", []), value.get("states", []), value.get("relations", []), value.get("constraints", [])):
            for item in registry:
                item_id = next((str(item[key]) for key in ("payload_id", "state_id", "relation_id", "constraint_id") if key in item), "")
                if item_id in selected: refs.update(map(str, item.get("evidence_refs", item.get("provenance_refs", []))))
        selected.update(refs)
    if selector.get("include_dependency_closure"):
        changed = True
        while changed:
            before = len(selected)
            for edge in value.get("dependency_graph", []):
                if edge.get("source_id") in selected or edge.get("target_id") in selected: selected.update([str(edge.get("source_id")), str(edge.get("target_id"))])
            changed = len(selected) != before
    return selected


def select_file(source: Path, selector: dict[str, Any], target: Path, *, overwrite: bool = False) -> dict[str, Any]:
    value = read_file(source); selected = _selected_ids(value, selector); partial = copy.deepcopy(value)
    registry_keys = {"units": "entity_id", "payloads": "payload_id", "states": "state_id", "relations": "relation_id", "constraints": "constraint_id", "evidence_registry": "evidence_id", "projection_descriptors": "projection_id", "external_resources": "resource_id"}
    omitted: list[str] = []
    for registry, key in registry_keys.items():
        records = partial.get(registry, []); omitted.extend(str(item.get(key)) for item in records if str(item.get(key)) not in selected); partial[registry] = [item for item in records if str(item.get(key)) in selected]
    partial["dependency_graph"] = [edge for edge in partial.get("dependency_graph", []) if edge.get("source_id") in selected and edge.get("target_id") in selected]
    partial["root_units"] = [unit_id for unit_id in partial.get("root_units", []) if unit_id in selected]
    partial.setdefault("partial_loading", {}).update({"is_partial": True, "selection_query_digest": "sha256:" + _sha(canonical_json_bytes(selector)), "included_entity_ids": sorted(selected), "omitted_entities": sorted(omitted), "entity_status": {entity_id: "not_loaded" for entity_id in sorted(omitted)}, "self_validating_selected_view": True, "source_complete_file_digest": "sha256:" + _sha(source.read_bytes())})
    return write_file(partial, target, overwrite=overwrite, partial=True)


def _safe_locator(locator: str) -> bool:
    if not locator or "\x00" in locator or "\\" in locator or re.match(r"^[A-Za-z]:", locator) or locator.startswith("/") or "?" in locator or "#" in locator: return False
    parts = PurePosixPath(locator).parts
    return all(part not in {"", ".", ".."} for part in parts)


def verify_resources(path: Path, resource_root: Path) -> dict[str, Any]:
    value = read_file(path); root = resource_root.resolve(); results = []; ok = True
    for resource in value.get("external_resources", []):
        locator = str(resource.get("locator", "")); critical = bool(resource.get("critical", False))
        if not _safe_locator(locator): results.append({"resource_id": resource.get("resource_id"), "status": "UNSAFE", "code": "RUO-F1-025"}); ok = False; continue
        candidate = root.joinpath(*PurePosixPath(locator).parts)
        try: resolved = candidate.resolve(strict=True)
        except OSError:
            status = "MISSING_CRITICAL" if critical else "UNAVAILABLE"; results.append({"resource_id": resource.get("resource_id"), "status": status}); ok = ok and not critical; continue
        if root != resolved and root not in resolved.parents: results.append({"resource_id": resource.get("resource_id"), "status": "UNSAFE", "code": "RUO-F1-025"}); ok = False; continue
        payload = resolved.read_bytes(); valid = len(payload) == resource.get("byte_size") and hmac.compare_digest(_sha(payload), str(resource.get("content_sha256", "")))
        results.append({"resource_id": resource.get("resource_id"), "status": "VERIFIED" if valid else "CORRUPT"}); ok = ok and valid
        chunks = resource.get("chunks", []); offset = 0
        for index, chunk in enumerate(chunks):
            size = chunk.get("byte_size"); valid_chunk = chunk.get("index") == index and chunk.get("byte_offset") == offset and isinstance(size, int) and hmac.compare_digest(_sha(payload[offset:offset + size]), str(chunk.get("sha256", ""))); ok = ok and valid_chunk; offset += size if isinstance(size, int) else 0
        if chunks and offset != len(payload): ok = False
    return {"ok": ok, "resource_root": str(root), "results": results, "external_resource_status": "VERIFIED" if ok else "FAILED"}
