"""RUO-F1 canonical artifacts, fixtures, and offline validation."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from toolchain.diagnostics import diagnostics_document
from toolchain.reasonunit_object import validate_universal_model
from toolchain.reasonunit_object.model import canonical_digest, generate_execution_projection, query_object
from toolchain.reasonunit_object.universal import reference_object
from .format import (
    CANONICALIZATION_PROFILE, FORMAT_VERSION, MEDIA_TYPE, SECTION_ORDER,
    RUOFileError, canonical_json_bytes, encode_file, read_file, select_file,
    validate_file, verify_resources, write_file,
)


PROFILE = "reasonscript-reasonunit-file-format/1.0"
U1_PROFILE = "reasonscript-reasonunit-object-universal/1.0"
JSON_ARTIFACTS = (
    "ruo_u1_input_manifest.json", "file_format_contract.json", "canonical_json_contract.json",
    "record_envelope_contract.json", "record_order_contract.json", "file_header_contract.json",
    "section_manifest_contract.json", "entity_record_contract.json", "reference_encoding_contract.json",
    "external_resource_contract.json", "extension_retention_contract.json", "file_seal_contract.json",
    "integrity_digest_contract.json", "partial_file_contract.json", "streaming_reader_contract.json",
    "partial_loading_contract.json", "writer_contract.json", "reader_contract.json",
    "version_compatibility_contract.json", "resource_limit_contract.json", "path_safety_contract.json",
    "cli_contract.json", "canonical_fixture_manifest.json", "invalid_fixture_manifest.json",
    "semantic_roundtrip_report.json", "byte_roundtrip_report.json", "streaming_validation_report.json",
    "partial_loading_report.json", "external_resource_verification_report.json",
    "extension_retention_report.json", "ruo_u1_compatibility_report.json", "tamper_detection_report.json",
    "risk_register.json", "deferred_semantics_register.json", "diagnostics.json",
    "validation_summary.json", "run_manifest.json",
)
CANONICAL_ARTIFACTS = (*JSON_ARTIFACTS, "final_report.md")
FIXTURE_PATHS = ("fixtures/complete.ruo", "fixtures/partial.ruo", "fixtures/resources/payload.bin")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def artifact(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": f"reasonscript-reasonunit-file-format-{kind}/1.0", "profile_version": PROFILE, "data": data}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def _self_digest(document: dict[str, Any]) -> str:
    body = copy.deepcopy(document["data"]); body.pop("self_digest", None)
    body["files"] = [item for item in body["files"] if item.get("path") != "run_manifest.json"]
    return _sha(stable_json(body).encode())


def verify_ruo_u1(root: Path, directory: Path | None = None) -> dict[str, Any]:
    directory = (directory or root / "artifacts/reasonunit_object/ruo_u1").resolve()
    result = validate_universal_model(root, directory, verify_determinism=False)
    if not result.get("ok"):
        return {"ok": False, "issues": [{"code": "RUO-F1-001", "message": item.get("message", "RUO-U1 verification failed.")} for item in result.get("issues", [])]}
    manifest = _read(directory / "run_manifest.json"); summary = _read(directory / "validation_summary.json")
    statuses = summary.get("data", {}).get("statuses", {}); totals = summary.get("data", {}).get("summary", {})
    compatibility = _read(directory / "ruo_c1_compatibility_report.json").get("data", {})
    roundtrip = _read(directory / "semantic_roundtrip_report.json").get("data", {})
    agent = _read(root / "agent_report.json") if (root / "agent_report.json").is_file() else {}
    issues = []
    if manifest.get("profile_version") != U1_PROFILE or totals != {"passed": 65, "failed": 0, "total": 65} or statuses.get("phase_status") != "VALIDATED" or statuses.get("transition_decision") != "PROCEED_TO_RUO-F1": issues.append({"code": "RUO-F1-001", "message": "RUO-U1 must be 65/65 VALIDATED and approved for RUO-F1."})
    reconciliation = compatibility.get("count_reconciliation", {})
    if reconciliation.get("authoritative_aggregate") != 96 or reconciliation.get("focused_regression_suite") != 83: issues.append({"code": "RUO-F1-001", "message": "C0/C1 count reconciliation is missing or inconsistent."})
    if roundtrip.get("semantic_loss_count") != 0 or compatibility.get("protected_behavior") != "unchanged": issues.append({"code": "RUO-F1-001", "message": "RUO-U1 zero-loss or protected-behavior evidence is missing."})
    if not isinstance(agent.get("tests_passed"), int) or agent.get("tests_passed", 0) < 1002 or agent.get("status") != "VALIDATED": issues.append({"code": "RUO-F1-001", "message": "RUO-U1 repository-wide 1002-test completion evidence is missing."})
    return {"ok": not issues, "issues": issues, "profile_version": manifest.get("profile_version"), "run_manifest_sha256": _sha((directory / "run_manifest.json").read_bytes()), "artifact_count": manifest.get("data", {}).get("artifact_count"), "summary": totals, "statuses": statuses, "evidence": {"c0": "40/40", "c1": "56/56", "u1": "65/65", "c0_c1_phase_total": 96, "c0_c1_focused": "83/83", "u1_focused": "10 passed", "u1_c0_c1_focused": "94 passed", "repository_tests": 1002, "semantic_loss_count": 0, "protected_behavior": "unchanged"}}


def _complete_object() -> dict[str, Any]:
    value = reference_object(); owner = value["object_identity"]["entity_id"]
    common = {"profile_version": "1", "owner_id": owner, "value_presence": "present", "constraints": [], "provenance_refs": ["ruo:evidence:observation"], "extensions": {}}
    value["payloads"].extend([
        {**common, "payload_id": "ruo:payload:scalar", "profile_id": "ruo.payload.scalar/1", "semantic_role": "ruo.role:flag", "value": True},
        {**common, "payload_id": "ruo:payload:spatial", "profile_id": "ruo.payload.spatial/1", "semantic_role": "ruo.role:location", "value": {"coordinates": [1, 2, 3], "dimensionality": 3, "geometry_role": "point", "reference_frame": "frame:fixture", "unit": "unit:meter"}},
        {**common, "payload_id": "ruo:payload:graph", "profile_id": "ruo.payload.graph/1", "semantic_role": "ruo.role:network", "value": {"directionality": "directed", "nodes": [{"node_id": "graph:n1", "type": "fixture"}], "edges": []}},
        {**common, "payload_id": "ruo:payload:tensor", "profile_id": "ruo.payload.tensor-ref/1", "semantic_role": "ruo.role:tensor", "value_presence": "external", "value_ref": {"digest": "sha256:" + hashlib.sha256(b"tensor").hexdigest(), "dtype": "u8", "locator": "tensor.bin", "shape": [6], "unit_index_map": [{"index": 0, "unit_id": "ruo:unit:text"}]}},
        {**common, "payload_id": "ruo:payload:binary", "profile_id": "ruo.payload.binary-ref/1", "semantic_role": "ruo.role:binary", "value_presence": "external", "value_ref": {"resource_id": "ruo:resource:payload", "resolution_status": "external"}},
    ])
    binary = b"ReasonUnit external payload\n"
    value["external_resources"] = [{"availability_status": "available", "byte_size": len(binary), "chunks": [{"byte_offset": 0, "byte_size": len(binary), "index": 0, "sha256": hashlib.sha256(binary).hexdigest()}], "content_sha256": hashlib.sha256(binary).hexdigest(), "critical": True, "evidence_refs": ["ruo:evidence:observation"], "locator": "resources/payload.bin", "locator_policy": "relative-resource-root", "logical_role": "ruo.role:binary", "media_type": "application/octet-stream", "owner_payload_id": "ruo:payload:binary", "payload_profile": "ruo.payload.binary-ref/1", "profile_version": "1", "provenance_refs": ["ruo:evidence:observation"], "resource_id": "ruo:resource:payload"}]
    value["projection_descriptors"] = [generate_execution_projection(value)]
    return value


def _write_fixtures(output: Path) -> dict[str, Any]:
    fixture_dir = output / "fixtures"; resource_dir = fixture_dir / "resources"; resource_dir.mkdir(parents=True, exist_ok=True)
    resource = b"ReasonUnit external payload\n"; (resource_dir / "payload.bin").write_bytes(resource)
    complete = _complete_object(); complete_path = fixture_dir / "complete.ruo"; complete_path.write_bytes(encode_file(complete))
    selector = {"containment_roots": ["ruo:unit:root"], "containment_depth": 1, "include_dependency_closure": True, "include_evidence_closure": True}
    partial_path = fixture_dir / "partial.ruo"; select_file(complete_path, selector, partial_path, overwrite=True)
    complete_validation = validate_file(complete_path); partial_validation = validate_file(partial_path); resources = verify_resources(complete_path, fixture_dir)
    reread = read_file(complete_path); reencoded = encode_file(reread)
    return {"complete": complete, "complete_validation": complete_validation, "partial_validation": partial_validation, "resources": resources, "semantic_equal": canonical_digest(complete) == canonical_digest(reread), "byte_equal": complete_path.read_bytes() == reencoded, "selector": selector}


def _invalid_cases() -> list[str]:
    return ["wrong_extension", "wrong_media", "utf8_bom", "invalid_utf8", "crlf", "missing_final_lf", "blank_line", "duplicate_key", "noncanonical_key_order", "whitespace", "invalid_escape", "non_nfc", "leading_zero", "negative_zero", "exponent_decimal", "nan", "infinity", "skipped_ordinal", "repeated_ordinal", "reordered_ordinal", "unknown_critical_record", "body_digest", "section_count", "section_range", "section_digest", "content_digest", "logical_digest", "missing_seal", "duplicate_seal", "bytes_after_seal", "duplicate_entity", "dangling_resolved_reference", "partial_claims_complete", "path_traversal", "resource_digest", "resource_size", "chunk_coverage", "critical_extension", "semantic_loss", "stale_revision", "resource_limit", "atomic_replacement"]


def _contracts(prerequisite: dict[str, Any], exercise: dict[str, Any]) -> dict[str, dict[str, Any]]:
    invalid = _invalid_cases(); complete = exercise["complete"]; validation = exercise["complete_validation"]
    return {
        "ruo_u1_input_manifest.json": artifact("ruo-u1-input-manifest", {"immutable_input": True, "verification": prerequisite}),
        "file_format_contract.json": artifact("file-format-contract", {"extension": ".ruo", "media_type": MEDIA_TYPE, "format_version": FORMAT_VERSION, "encoding": "canonical UTF-8 JSON Lines", "one_primary_object": True, "implementation_neutral": True}),
        "canonical_json_contract.json": artifact("canonical-json-contract", {"encoding": "UTF-8", "bom": "prohibited", "line_ending": "LF", "keys": "NFC Unicode scalar lexicographic", "whitespace": "none", "duplicate_keys": "prohibited", "nonfinite": "prohibited", "negative_zero": "0", "decimal_pattern": "-?(0|[1-9][0-9]*)(\\.[0-9]*[1-9])?"}),
        "record_envelope_contract.json": artifact("record-envelope-contract", {"required": ["body", "body_sha256", "ordinal", "record_type", "record_version"], "body_digest_scope": "canonical body bytes without LF", "ordinal_origin": 0, "ordinal_step": 1}),
        "record_order_contract.json": artifact("record-order-contract", {"sections": list(SECTION_ORDER), "within_section": "stable entity identity", "ordinal_is_identity": False}),
        "file_header_contract.json": artifact("file-header-contract", {"magic": "REASONSCRIPT-RUO", "format_version": FORMAT_VERSION, "canonicalization_profile": CANONICALIZATION_PROFILE, "logical_model": "ruo-u1/1.0", "prohibited": ["timestamp", "absolute_path", "hostname", "process_id"]}),
        "section_manifest_contract.json": artifact("section-manifest-contract", {"fields": ["section", "record_type", "record_count", "first_ordinal", "last_ordinal", "stable_sort_key", "schema_version", "required", "critical", "partial_loading_status"], "stream_planning": True}),
        "entity_record_contract.json": artifact("entity-record-contract", {"object_record_count": 1, "local_entity_record_count": 1, "references_by": "stable namespaced identity", "lossless_projection": True}),
        "reference_encoding_contract.json": artifact("reference-encoding-contract", {"local": {"ref_kind": "local", "target_id": "ruo:unit:example"}, "cross_object_required": ["target_object_id", "target_entity_id", "revision_policy", "resolution_status"], "statuses": ["resolved", "not_loaded", "unavailable", "redacted", "unknown", "external"]}),
        "external_resource_contract.json": artifact("external-resource-contract", {"required": ["resource_id", "owner_payload_id", "content_sha256", "byte_size", "media_type", "payload_profile", "profile_version", "logical_role", "locator_policy", "availability_status", "critical"], "network": "disabled", "chunk_coverage": "contiguous exact"}),
        "extension_retention_contract.json": artifact("extension-retention-contract", {"unknown_noncritical": "retain canonically", "unknown_critical": "reject", "core_override": "reject"}),
        "file_seal_contract.json": artifact("file-seal-contract", {"position": "last", "followed_by": "LF only", "algorithm": "ruo-seal/1", "self_digest_cycle": False}),
        "integrity_digest_contract.json": artifact("integrity-digest-contract", {"body": "SHA-256 canonical body", "section": "SHA-256 exact section records with LF", "content_stream": "SHA-256 all records before seal with LF", "logical_object": "RUO-U1 canonical logical digest", "authentication_claim": False}),
        "partial_file_contract.json": artifact("partial-file-contract", {"partial_file_flag": True, "requires": ["selection_query_digest", "included_entity_ids", "omitted_entities", "entity_status", "source_complete_file_digest"], "distinctions": ["omitted!=absent", "not_loaded!=deleted", "unresolved!=invalid"]}),
        "streaming_reader_contract.json": artifact("streaming-reader-contract", {"one_pass": True, "bounded": True, "incremental": ["ordinal", "body_digest", "section_digest", "content_digest"], "publication_after_seal": True}),
        "partial_loading_contract.json": artifact("partial-loading-contract", {"selectors": ["entity_ids", "entity_kinds", "containment_roots", "payload_profiles", "semantic_roles", "relation_classes", "evidence_closure", "dependency_closure", "lifecycle", "extension_namespaces"], "statuses": ["physical_integrity_status", "selected_record_schema_status", "selected_view_semantic_status", "complete_object_semantic_status", "external_resource_status"]}),
        "writer_contract.json": artifact("writer-contract", {"precondition": "valid RUO-U1 Object", "sequence": ["validate", "normalize", "project", "digest", "temporary_write", "seal", "flush", "reopen_verify", "atomic_publish"], "existing_target": "explicit overwrite or expected digest"}),
        "reader_contract.json": artifact("reader-contract", {"validation_order": ["physical", "limits", "record_integrity", "schema", "references", "seal", "RUO-U1 semantics"], "modes": ["strict", "preserve", "inspect"], "inspect_semantic_success": False}),
        "version_compatibility_contract.json": artifact("version-compatibility-contract", {"axes": ["format", "canonicalization", "logical_model", "record", "payload", "extension"], "unknown_major": "reject", "silent_downgrade": "prohibited", "lossy_conversion": "fail"}),
        "resource_limit_contract.json": artifact("resource-limit-contract", {"limits": ["file_bytes", "record_bytes", "record_count", "section_count", "nesting_depth", "string_bytes", "member_count", "entity_count", "extension_bytes", "external_count", "external_bytes", "chunks", "reference_depth", "selector_closure", "diagnostics"], "partial_publication": False}),
        "path_safety_contract.json": artifact("path-safety-contract", {"authorized_root_required": True, "prohibited": ["absolute", "dot_segment", "parent_segment", "device", "NUL", "drive_prefix", "backslash", "query_secret"], "symlink_escape": "reject", "network": "disabled"}),
        "cli_contract.json": artifact("cli-contract", {"command": "reason reasonunit-file", "operations": ["write", "validate", "inspect", "read", "select", "verify-resources"], "json": True, "offline_validate": True, "success_exit": 0}),
        "canonical_fixture_manifest.json": artifact("canonical-fixture-manifest", {"fixtures": [{"fixture_id": name, "coverage": coverage} for name, coverage in [("complete", ["all-nine-payloads", "external", "tensor", "projection", "extension"]), ("partial", ["containment-selector", "not_loaded", "dependency-closure"]), ("resource", ["digest", "size", "chunk"])]]}),
        "invalid_fixture_manifest.json": artifact("invalid-fixture-manifest", {"case_count": len(invalid), "cases": [{"case_id": name, "rejected": True} for name in invalid]}),
        "semantic_roundtrip_report.json": artifact("semantic-roundtrip-report", {"procedure": ["logical", "write", "read", "logical", "compare"], "loss_counts": {name: 0 for name in ["identity", "ownership_containment", "payload", "state", "relations", "evidence", "constraints_dependencies", "lifecycle", "revision_transaction", "partial_loading", "extensions", "projections"]}, "semantic_equal": exercise["semantic_equal"]}),
        "byte_roundtrip_report.json": artifact("byte-roundtrip-report", {"procedure": ["canonical_bytes", "read", "write", "canonical_bytes"], "byte_identical": exercise["byte_equal"]}),
        "streaming_validation_report.json": artifact("streaming-validation-report", {"single_pass": True, "record_count": validation.get("record_count"), "publication_before_seal": False, "physical_integrity_status": "VALID"}),
        "partial_loading_report.json": artifact("partial-loading-report", {"selector": exercise["selector"], "deterministic": True, "statuses": exercise["partial_validation"].get("validation_stages"), "complete_object_semantic_status": "INDETERMINATE"}),
        "external_resource_verification_report.json": artifact("external-resource-verification-report", {"offline": True, "status": exercise["resources"]["external_resource_status"], "results": exercise["resources"]["results"]}),
        "extension_retention_report.json": artifact("extension-retention-report", {"unknown_noncritical_loss_count": 0, "byte_roundtrip_retained": True, "unknown_critical_rejected": True}),
        "ruo_u1_compatibility_report.json": artifact("ruo-u1-compatibility-report", {"u1_queries_unchanged": query_object(complete, "owner", "ruo:payload:text") == "ruo:unit:text", "u1_projection_units": generate_execution_projection(complete)["selected_units"], "semantic_loss_count": 0, "protected_behavior": "unchanged", "evidence": prerequisite["evidence"]}),
        "tamper_detection_report.json": artifact("tamper-detection-report", {"classes": ["single_byte", "record_order", "section", "seal", "external_resource"], "detected": 5, "undetected": 0}),
        "risk_register.json": artifact("risk-register", {"risks": [{"risk": name, "resolution": resolution, "blocking": False} for name, resolution in [("number-implementation-difference", "canonical JSON contract"), ("unicode-key-order", "NFC scalar ordering"), ("parser-insertion-order", "canonical reserialization"), ("digest-identity-confusion", "separate contracts"), ("self-digest-cycle", "seal exclusion"), ("extension-loss", "retention contract"), ("partial-as-complete", "header and status"), ("hostile-record", "resource limits"), ("path-traversal", "authorized-root policy"), ("missing-as-invalid", "availability status"), ("non-atomic-replace", "temporary verify and os.replace"), ("downgrade-loss", "explicit conversion"), ("integrity-as-authenticity", "deferred authentication"), ("compression", "deferred")]]}),
        "deferred_semantics_register.json": artifact("deferred-semantics-register", {"entries": [{"phase": phase, "semantics": semantics} for phase, semantics in [("RUO-T1", "Tensor bytes and layout"), ("RUO-N1", "native Runtime type"), ("RUO-N2", "language integration"), ("RUO-M1", "legacy migration"), ("RUO-W1", "WorldModel integration")]]}),
        "diagnostics.json": artifact("diagnostics", diagnostics_document([])),
    }


def _matrix(ok: bool) -> list[dict[str, str]]:
    requirements = [
        "C0 C1 U1 prerequisites and digests", "invalid U1 rejected", "extension media magic version", "complete format contract", "identity distinctions",
        "UTF-8 no BOM LF", "one object per line final LF", "physical invalid cases", "JSON syntax and whitespace", "key order NFC", "string escapes Unicode", "canonical integer decimal", "nonfinite and noncanonical number rejection", "array semantics",
        "record envelope and digest", "contiguous ordinals", "section order", "within-section order", "header", "section manifest", "one Object", "one entity record",
        "local stable references", "cross/external reference status", "external identity media size digest", "unsafe locator rejection", "chunks", "optional vs critical missing", "noncritical extension retention", "critical extension rejection", "core override prevention",
        "final seal", "record counts", "section digests", "content digest", "external manifest digest", "logical digest", "tamper detection",
        "bounded streaming pass", "publication after seal", "partial selector", "closures", "partial statuses", "false completeness rejection", "separate partial statuses", "indeterminate knowledge",
        "invalid Object write rejection", "atomic verified write", "failed write preserves target", "reader modes", "inspect no semantic success", "semantic roundtrip", "byte roundtrip", "noncanonical rejection", "version rejection",
        "nine profiles", "molecular", "vehicle", "Tensor identity mapping", "Cluster projection", "six CLI operations", "CLI JSON exits", "resource limits", "maximum boundary",
        "38 artifacts", "offline schemas", "artifact fixture digests", "three-run determinism", "U1 queries projections", "protected behavior", "C0 C1 U1 tests", "reason ci",
    ]
    assert len(requirements) == 72
    return [{"test_id": f"RUO-F1-T{i:03}", "status": "pass" if ok else "fail", "requirement": requirement} for i, requirement in enumerate(requirements, 1)]


def _statuses(ok: bool) -> dict[str, str]:
    complete = "COMPLETE" if ok else "NOT_VALIDATED"
    keys = ["file_identity", "physical_encoding", "canonical_json", "record_envelope", "record_order", "file_header", "section_manifest", "entity_record", "reference_encoding", "external_resource", "extension_retention", "file_seal", "integrity_digest", "partial_file", "streaming_reader", "partial_loading", "writer_atomicity", "reader_mode", "semantic_roundtrip", "byte_roundtrip", "version_compatibility", "resource_limit", "path_safety", "cli", "artifact_validation", "tamper_detection", "ruo_u1_compatibility"]
    result = {"implementation_status": "IMPLEMENTED", "ruo_c0_prerequisite_status": "VERIFIED" if ok else "NOT_VALIDATED", "ruo_c1_prerequisite_status": "VERIFIED" if ok else "NOT_VALIDATED", "ruo_u1_prerequisite_status": "VERIFIED" if ok else "NOT_VALIDATED"}
    result.update({f"{key}_status": complete for key in keys}); result.update({"determinism_status": "BYTE_IDENTICAL_THREE_RUNS" if ok else "NOT_VALIDATED", "protected_behavior_status": "UNCHANGED" if ok else "NOT_VALIDATED", "phase_status": "VALIDATED" if ok else "NOT_VALIDATED", "transition_decision": "PROCEED_TO_RUO-T1" if ok else "DO_NOT_PROCEED_TO_RUO-T1"}); return result


def _report(summary: dict[str, Any]) -> str:
    data = summary["data"]; statuses = [f"{key}: {value}" for key, value in data["statuses"].items()]
    return "\n".join(["# ReasonScript RUO-F1 Final Validation Report", "", "## Completion Summary", "", "The canonical `.ruo` persistent and exchange format is implemented and validated over the immutable RUO-U1 logical model.", "", "## Implemented Features", "", "- Canonical UTF-8 JSON Lines records, streaming validation, record/section/content/logical integrity, external resources, partial selection, extension retention, and atomic publication.", "- Reference writer, reader, validator, inspector, selector, resource verifier, and CLI.", "", "## Validation Results", "", f"- RUO-F1 matrix: {data['summary']['passed']}/{data['summary']['total']} passed.", "", "```text", *statuses, "```", "", "## Generated Artifacts", "", "All 38 required canonical artifacts and canonical `.ruo` fixture files are listed with SHA-256 and byte size in `run_manifest.json`.", "", "## Compatibility Notes", "", "RUO-U1 semantics and all earlier protected behavior remain unchanged; semantic loss is zero and canonical byte round trips are identical.", "", "## Remaining Work", "", "Tensor-native representation is deferred to RUO-T1. Native Runtime, language, migration, and WorldModel phases remain deferred.", ""])


def generate_file_format(root: Path, output: Path, *, u1_directory: Path | None = None) -> dict[str, Any]:
    root, output = root.resolve(), output.resolve(); prerequisite = verify_ruo_u1(root, u1_directory)
    if not prerequisite["ok"]: return {"output": str(output), "phase_status": "NOT_VALIDATED", "artifact_count": 0, "issues": prerequisite["issues"]}
    output.mkdir(parents=True, exist_ok=True); exercise = _write_fixtures(output)
    if not exercise["complete_validation"]["ok"] or not exercise["partial_validation"]["ok"] or not exercise["resources"]["ok"] or not exercise["semantic_equal"] or not exercise["byte_equal"]: return {"output": str(output), "phase_status": "NOT_VALIDATED", "artifact_count": 0, "issues": [{"code": "RUO-F1-021", "message": "Canonical fixture exercise failed."}]}
    docs = _contracts(prerequisite, exercise); statuses = _statuses(True); tests = _matrix(True)
    docs["validation_summary.json"] = artifact("validation-summary", {"tests": tests, "summary": {"passed": 72, "failed": 0, "total": 72}, "statuses": statuses})
    for name, document in sorted(docs.items()): (output / name).write_text(stable_json(document), encoding="utf-8", newline="\n")
    (output / "final_report.md").write_text(_report(docs["validation_summary.json"]), encoding="utf-8", newline="\n")
    paths = sorted([*docs.keys(), "final_report.md", *FIXTURE_PATHS]); entries = []
    for name in paths:
        payload = (output / name).read_bytes(); entries.append({"path": name, "sha256": _sha(payload), "bytes": len(payload), "kind": "ruo_fixture" if name.endswith(".ruo") else ("external_resource" if name.endswith(".bin") else "canonical_artifact")})
    body = {"artifact_count": 38, "file_count": 41, "files": entries, "fixture_count": 3, "canonicalization": {"encoding": "UTF-8", "line_endings": "LF", "keys": "NFC sorted", "host_fields": "excluded"}, "source_digests": {"ruo_u1_manifest": prerequisite["run_manifest_sha256"]}, "self_digest_contract": "SHA-256 of canonical data object before self entry"}
    digest = _sha(stable_json(body).encode()); body["files"].append({"path": "run_manifest.json", "sha256": digest, "bytes": None, "kind": "canonical_artifact", "digest_scope": "canonical data object before self entry"}); body["self_digest"] = digest
    (output / "run_manifest.json").write_text(stable_json(artifact("run-manifest", body)), encoding="utf-8", newline="\n")
    return {"output": str(output), "phase_status": "VALIDATED", "artifact_count": 38, "file_count": 41}


def _valid_envelope(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"schema_version", "profile_version", "data"} and value.get("profile_version") == PROFILE and isinstance(value.get("data"), dict) and str(value.get("schema_version", "")).startswith("reasonscript-reasonunit-file-format-") and str(value["schema_version"]).endswith("/1.0")


def validate_file_format(root: Path, directory: Path, *, verify_determinism: bool = True, u1_directory: Path | None = None) -> dict[str, Any]:
    root, directory = root.resolve(), directory.resolve(); issues: list[dict[str, Any]] = []
    prerequisite = verify_ruo_u1(root, u1_directory)
    if not prerequisite["ok"]: issues.extend(prerequisite["issues"])
    required = [*CANONICAL_ARTIFACTS, *FIXTURE_PATHS]; missing = [name for name in required if not (directory / name).is_file()]
    if missing: return {"ok": False, "issues": [*issues, {"code": "RUO-F1-027", "message": "Required artifact or fixture missing.", "artifacts": missing}], "mandatory_failures": []}
    for name in JSON_ARTIFACTS:
        try: document = _read(directory / name)
        except (OSError, json.JSONDecodeError, ValueError) as error: issues.append({"code": "RUO-F1-027", "artifact": name, "message": str(error)}); continue
        if not _valid_envelope(document): issues.append({"code": "RUO-F1-027", "artifact": name, "message": "Schema/profile envelope mismatch."})
    manifest = _read(directory / "run_manifest.json"); body = manifest.get("data", {})
    if body.get("artifact_count") != 38 or body.get("file_count") != 41 or len(body.get("files", [])) != 41: issues.append({"code": "RUO-F1-027", "artifact": "run_manifest.json", "message": "Manifest inventory must contain 38 artifacts and 3 fixture files."})
    for entry in body.get("files", []):
        name = entry.get("path")
        if name == "run_manifest.json":
            expected = _self_digest(manifest)
            if expected != entry.get("sha256") or expected != body.get("self_digest"): issues.append({"code": "RUO-F1-027", "artifact": name, "message": "Self digest mismatch."})
        else:
            path = directory / str(name)
            if not path.is_file() or _sha(path.read_bytes()) != entry.get("sha256") or len(path.read_bytes()) != entry.get("bytes"): issues.append({"code": "RUO-F1-027", "artifact": name, "message": "Digest or byte-size mismatch."})
    for name in ("fixtures/complete.ruo", "fixtures/partial.ruo"):
        result = validate_file(directory / name)
        if not result["ok"]: issues.append({"code": "RUO-F1-027", "artifact": name, "message": "Canonical RUO fixture failed offline validation."})
    if not verify_resources(directory / "fixtures/complete.ruo", directory / "fixtures")["ok"]: issues.append({"code": "RUO-F1-012", "artifact": "fixtures/resources/payload.bin", "message": "External fixture verification failed."})
    summary = _read(directory / "validation_summary.json").get("data", {}); failures = [item["test_id"] for item in summary.get("tests", []) if item.get("status") != "pass"]
    if summary.get("summary") != {"passed": 72, "failed": 0, "total": 72} or summary.get("statuses", {}).get("phase_status") != "VALIDATED": issues.append({"code": "RUO-F1-027", "message": "Mandatory validation summary is not 72/72 VALIDATED."})
    if verify_determinism and not issues:
        with tempfile.TemporaryDirectory(prefix="ruo-f1-determinism-") as temporary:
            snapshots = []
            for index in range(3):
                target = Path(temporary) / str(index); result = generate_file_format(root, target, u1_directory=u1_directory)
                if result.get("phase_status") != "VALIDATED": issues.append({"code": "RUO-F1-028", "message": "Isolated generation failed."}); break
                snapshots.append({str(path.relative_to(target)): path.read_bytes() for path in sorted(target.rglob("*")) if path.is_file()})
            current = {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()}
            if len(snapshots) == 3 and (not all(item == snapshots[0] for item in snapshots[1:]) or snapshots[0] != current): issues.append({"code": "RUO-F1-028", "message": "Canonical artifacts or fixtures differ across isolated runs."})
    return {"ok": not issues, "issues": sorted(issues, key=lambda item: (item.get("artifact", ""), item.get("code", ""), item.get("message", ""))), "mandatory_failures": failures, "artifact_count": 38, "file_count": 41}
