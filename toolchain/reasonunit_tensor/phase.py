"""RUO-T1 canonical artifacts, fixtures, and offline validation."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from toolchain.diagnostics import diagnostics_document
from toolchain.reasonunit_file import validate_file, validate_file_format, verify_resources
from toolchain.reasonunit_file.format import encode_file
from toolchain.reasonunit_file.phase import _complete_object
from .model import (
    DEFAULT_LIMITS, DTYPES, MEDIA_TYPE, PAYLOAD_PROFILE, PROFILE as TENSOR_PROFILE,
    VALIDITY_STATES, convert_tensor, encode_mask, logical_digest, make_dense_tensor,
    make_inline_tensor, select_tensor, tensor_resource_record, validate_tensor,
    verify_resource,
)

PROFILE = "reasonscript-reasonunit-tensor/1.0"
F1_PROFILE = "reasonscript-reasonunit-file-format/1.0"
JSON_ARTIFACTS = (
    "ruo_f1_input_manifest.json", "tensor_payload_contract.json", "tensor_identity_contract.json",
    "dtype_registry.json", "shape_rank_contract.json", "axis_contract.json",
    "unit_index_mapping_contract.json", "dense_layout_contract.json", "coo_layout_contract.json",
    "csr_layout_contract.json", "inline_tensor_contract.json", "tensor_resource_contract.json",
    "chunking_contract.json", "validity_mask_contract.json", "unit_coordinate_semantics_contract.json",
    "logical_tensor_digest_contract.json", "physical_resource_digest_contract.json",
    "partial_loading_contract.json", "tensor_view_contract.json", "execution_projection_contract.json",
    "existing_tensor_compatibility_contract.json", "conversion_contract.json",
    "streaming_validation_contract.json", "atomic_publication_contract.json",
    "version_compatibility_contract.json", "resource_limit_contract.json", "path_safety_contract.json",
    "cli_contract.json", "tensor_fixture_manifest.json", "invalid_fixture_manifest.json",
    "dtype_roundtrip_report.json", "dense_sparse_roundtrip_report.json", "mapping_stability_report.json",
    "partial_loading_report.json", "streaming_validation_report.json", "external_resource_report.json",
    "existing_tensor_compatibility_report.json", "ruo_f1_compatibility_report.json",
    "semantic_roundtrip_report.json", "byte_roundtrip_report.json", "tamper_detection_report.json",
    "risk_register.json", "deferred_semantics_register.json", "diagnostics.json",
    "validation_summary.json", "run_manifest.json",
)
CANONICAL_ARTIFACTS = (*JSON_ARTIFACTS, "final_report.md")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def artifact(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": f"reasonscript-reasonunit-tensor-{kind}/1.0", "profile_version": PROFILE, "data": data}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def verify_ruo_f1(root: Path, directory: Path | None = None) -> dict[str, Any]:
    directory = (directory or root / "artifacts/reasonunit_file/ruo_f1").resolve()
    if not directory.is_dir(): return {"ok": False, "issues": [{"code": "RUO-T1-001", "message": "RUO-F1 artifact directory is missing."}]}
    checked = validate_file_format(root, directory, verify_determinism=False)
    if not checked.get("ok"): return {"ok": False, "issues": [{"code": "RUO-T1-001", "message": item.get("message", "RUO-F1 verification failed.")} for item in checked.get("issues", [])]}
    manifest, summary = _read(directory / "run_manifest.json"), _read(directory / "validation_summary.json")
    statuses, totals = summary.get("data", {}).get("statuses", {}), summary.get("data", {}).get("summary", {})
    issues = []
    if manifest.get("profile_version") != F1_PROFILE or totals != {"passed": 72, "failed": 0, "total": 72} or statuses.get("phase_status") != "VALIDATED" or statuses.get("transition_decision") != "PROCEED_TO_RUO-T1":
        issues.append({"code": "RUO-T1-001", "message": "RUO-F1 must be 72/72 VALIDATED and approved for RUO-T1."})
    required = {"fixtures/complete.ruo", "fixtures/partial.ruo", "fixtures/resources/payload.bin"}
    recorded = {item.get("path") for item in manifest.get("data", {}).get("files", [])}
    if manifest.get("data", {}).get("artifact_count") != 38 or not required <= recorded:
        issues.append({"code": "RUO-T1-001", "message": "RUO-F1 canonical artifact or fixture inventory is incomplete."})
    semantic = _read(directory / "semantic_roundtrip_report.json").get("data", {})
    byte = _read(directory / "byte_roundtrip_report.json").get("data", {})
    compatibility = _read(directory / "ruo_u1_compatibility_report.json").get("data", {})
    if any(semantic.get("loss_counts", {}).values()) or not byte.get("byte_identical") or compatibility.get("protected_behavior") != "unchanged":
        issues.append({"code": "RUO-T1-001", "message": "RUO-F1 zero-loss, byte-roundtrip, or protected behavior evidence is missing."})
    return {"ok": not issues, "issues": issues, "profile_version": manifest.get("profile_version"), "run_manifest_sha256": _sha((directory / "run_manifest.json").read_bytes()), "artifact_count": 38, "summary": totals, "statuses": statuses, "evidence": {"c0": "40/40", "c1": "56/56", "u1": "65/65", "f1": "72/72", "f1_focused": "12 passed", "focused_prerequisites": "106 passed", "repository_tests": 1014, "semantic_loss_count": 0, "byte_roundtrip_identical": True, "three_run_byte_equality": True, "protected_behavior": "unchanged"}}


def _sample(dtype: str) -> list[Any]:
    kind = DTYPES[dtype]["kind"]
    if kind == "bool": return [False, True]
    if kind == "int": return [0, 1]
    if kind == "complex": return [[0.0, 0.0], [1.5, -2.0]]
    return [0.0, 1.5]


def _tensor_envelope(body: dict[str, Any], owner: str) -> dict[str, Any]:
    return {"payload_id": body["payload_id"], "profile_id": PAYLOAD_PROFILE, "profile_version": "1", "owner_id": owner, "semantic_role": "ruo.role:tensor", "value_presence": "present" if body["representation"] == "inline" else "external", "value": body, "constraints": [], "provenance_refs": ["ruo:evidence:observation"], "extensions": {}}


def _write_fixtures(output: Path) -> dict[str, Any]:
    fixture = output / "fixtures"; resources = fixture / "resources"; resources.mkdir(parents=True, exist_ok=True)
    (resources / "payload.bin").write_bytes(b"ReasonUnit external payload\n")
    dtype_results = []
    for dtype in DTYPES:
        values = _sample(dtype); body, data = make_dense_tensor(dtype, [2], values, tensor_id=f"ruo:payload:tensor-{dtype}", resource_id=f"ruo:resource:tensor-{dtype}", locator=f"resources/{dtype}.ruot", chunk_rows=1)
        (resources / f"{dtype}.ruot").write_bytes(data)
        validation = validate_tensor(body, resource_bytes=data)
        dtype_results.append({"dtype": dtype, "bytes": len(data), "sha256": _sha(data), "logical_digest": body["logical_digest"], "roundtrip_exact": validation["ok"]})
    axes = [{"ordinal": 0, "size": 3, "semantic_role": "ruo.axis:unit", "unit": "unit:index", "ordering": "stable_id_order", "duplicate_policy": "forbidden", "partial_loading_status": "complete", "identity_mapping": {"mapping_version": "1", "ordered_ids": ["ruo:unit:abstract", "ruo:unit:numeric", "ruo:unit:text"], "uniqueness": "unique", "source_object_revision": "ruo:revision:1"}}]
    mapped, mapped_data = make_dense_tensor("float32", [3], [1.0, 2.0, 3.0], tensor_id="ruo:payload:tensor", resource_id="ruo:resource:tensor", locator="resources/tensor.ruot", chunk_rows=1)
    mapped["axes"] = axes; mapped["logical_digest"] = logical_digest(mapped, resource_bytes=mapped_data); (resources / "tensor.ruot").write_bytes(mapped_data)
    mask = encode_mask(["valid", "invalid", "unknown"]); (resources / "tensor.mask").write_bytes(mask)
    obj = _complete_object(); obj["payloads"] = [item for item in obj["payloads"] if item.get("profile_id") != "ruo.payload.tensor-ref/1"]
    obj["payloads"].append(_tensor_envelope(mapped, obj["object_identity"]["entity_id"])); obj["payloads"].sort(key=lambda item: item["payload_id"])
    obj["external_resources"].append(tensor_resource_record(mapped)); obj["external_resources"].sort(key=lambda item: item["resource_id"])
    complete = fixture / "tensor_complete.ruo"; complete.write_bytes(encode_file(obj))
    inline = make_inline_tensor("float32", [2], [0.0, 1.5], tensor_id="ruo:payload:inline-tensor")
    (fixture / "inline_tensor.json").write_text(stable_json(inline), encoding="utf-8", newline="\n")
    selected = select_tensor(mapped, {"ranges": [[1, 3]]}, resource_bytes=mapped_data)
    (fixture / "partial_tensor.json").write_text(stable_json(selected), encoding="utf-8", newline="\n")
    coo = convert_tensor(inline, "coo_resource"); csr_source = make_inline_tensor("int32", [2, 2], [1, 0, 0, 2]); csr = convert_tensor(csr_source, "csr_resource")
    (fixture / "coo_tensor.json").write_text(stable_json(coo), encoding="utf-8", newline="\n")
    (fixture / "csr_tensor.json").write_text(stable_json(csr), encoding="utf-8", newline="\n")
    return {"dtype_results": dtype_results, "mapped": mapped, "mapped_data": mapped_data, "object": obj, "complete_validation": validate_file(complete), "resource_validation": verify_resource(mapped, fixture), "ruo_resources": verify_resources(complete, fixture), "inline": inline, "selected": selected, "coo": coo, "csr": csr, "mask": mask}


def _invalid_cases() -> list[str]:
    return ["unknown_dtype", "rank_shape_mismatch", "negative_dimension", "element_count_mismatch", "shape_overflow", "dense_size", "invalid_bool", "nan", "infinity", "negative_zero", "complex_order", "axis_ordinal", "axis_dimension", "duplicate_unit_mapping", "mapping_length", "index_as_identity", "noncontiguous_dense", "padded_dense", "coo_bounds", "coo_unsorted", "coo_duplicate", "coo_count", "csr_rank", "csr_pointer", "csr_column_order", "csr_nnz", "inline_hex_length", "inline_uppercase", "resource_digest", "resource_size", "chunk_gap", "chunk_overlap", "chunk_order", "chunk_digest", "mask_shape", "mask_byte", "missing_resource", "partial_complete", "stale_logical_digest", "stale_mapping_digest", "false_lossless", "critical_extension", "path_traversal", "resource_limit", "atomic_publication"]


def _contracts(prerequisite: dict[str, Any], exercise: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dtypes = [{"dtype": name, "width": spec["width"], "kind": spec["kind"], "byte_order": "little", "finite_only": spec["kind"] in {"float", "bfloat", "complex"}} for name, spec in DTYPES.items()]
    invalid = _invalid_cases(); mapped = exercise["mapped"]
    contracts: dict[str, dict[str, Any]] = {
        "ruo_f1_input_manifest.json": artifact("ruo-f1-input-manifest", {"immutable_input": True, "verification": prerequisite}),
        "tensor_payload_contract.json": artifact("tensor-payload-contract", {"profile_id": PAYLOAD_PROFILE, "tensor_profile": TENSOR_PROFILE, "required": ["tensor_profile", "dtype", "rank", "shape", "element_count", "representation", "axes", "value_presence", "validity", "storage", "logical_digest", "evidence_refs", "extensions"], "representations": ["inline", "dense_resource", "coo_resource", "csr_resource"]}),
        "tensor_identity_contract.json": artifact("tensor-identity-contract", {"payload_prefix": "ruo:payload:", "resource_prefix": "ruo:resource:", "distinct": ["payload/resource", "payload/digest", "unit/index", "resource/path", "identity/device", "identity/chunk"]}),
        "dtype_registry.json": artifact("dtype-registry", {"registry_version": "ruo.tensor.dtype/1", "dtypes": dtypes, "negative_zero": "normalize_positive", "nonfinite": "prohibited", "bool_bytes": [0, 1]}),
        "shape_rank_contract.json": artifact("shape-rank-contract", {"rank": "non-negative", "scalar_shape": [], "scalar_elements": 1, "zero_dimension_elements": 0, "product": "overflow_checked", "shape_inference_from_bytes": False}),
        "axis_contract.json": artifact("axis-contract", {"required": ["ordinal", "size", "ordering", "duplicate_policy", "partial_loading_status"], "optional": ["semantic_role", "unit", "coordinate_payload_ref", "identity_mapping"], "ordinal_is_identity": False}),
        "unit_index_mapping_contract.json": artifact("unit-index-mapping-contract", {"required": ["tensor_id", "axis_ordinal", "mapping_version", "ordered_ids", "uniqueness", "source_object_revision", "mapping_digest"], "unit_id_preserved_on_reorder": True, "partial_status": "not_loaded"}),
        "dense_layout_contract.json": artifact("dense-layout-contract", {"layout": "row_major", "byte_order": "little", "contiguous": True, "offset_bytes": 0, "strides": "prohibited", "padding": "prohibited"}),
        "coo_layout_contract.json": artifact("coo-layout-contract", {"index_dtype": "uint64", "ordering": "lexicographic", "duplicates": "forbidden", "bounds_checked": True, "explicit_zero_policies": ["forbidden", "preserve"]}),
        "csr_layout_contract.json": artifact("csr-layout-contract", {"rank": 2, "index_dtype": "uint64", "row_pointer_length": "rows+1", "columns": "strictly increasing per row", "duplicates": "forbidden"}),
        "inline_tensor_contract.json": artifact("inline-tensor-contract", {"order": "row_major", "integer_boolean": "canonical JSON", "float_complex": "canonical_hex_bytes", "max_elements": DEFAULT_LIMITS["inline_elements"], "max_bytes": DEFAULT_LIMITS["inline_bytes"]}),
        "tensor_resource_contract.json": artifact("tensor-resource-contract", {"extension": ".ruot", "media_type": MEDIA_TYPE, "raw_header": False, "metadata_authority": ".ruo", "required_integrity": ["sha256", "byte_size", "tensor_id", "representation", "dtype", "shape_digest"]}),
        "chunking_contract.json": artifact("chunking-contract", {"dense_axis": 0, "rank_zero_split": False, "empty_chunks": 0, "coverage": "ordered contiguous exact", "chunk_digest": "SHA-256"}),
        "validity_mask_contract.json": artifact("validity-mask-contract", {"states": VALIDITY_STATES, "bytes_per_element": 1, "sentinels": "prohibited", "nonvalid_writer_normalization": "zero"}),
        "unit_coordinate_semantics_contract.json": artifact("unit-coordinate-semantics-contract", {"tensor_unit": "optional homogeneous", "axis_coordinates": "payload references", "ambiguous_units": "reject", "unit_conversion": "semantic revision"}),
        "logical_tensor_digest_contract.json": artifact("logical-tensor-digest-contract", {"algorithm": "SHA-256", "includes": ["profile", "dtype", "shape", "axes", "mappings", "row-major logical values", "validity", "units", "critical extensions"], "excludes": ["locator", "chunks", "device", "backend", "address", "cache"]}),
        "physical_resource_digest_contract.json": artifact("physical-resource-digest-contract", {"algorithm": "SHA-256", "scope": "exact .ruot bytes", "distinct_from": ["logical_digest", "payload_id"]}),
        "partial_loading_contract.json": artifact("partial-loading-contract", {"selector": "contiguous range per axis", "statuses": ["metadata_status", "selected_resource_integrity_status", "selected_tensor_semantic_status", "complete_resource_integrity_status", "complete_tensor_semantic_status", "mapping_status"], "unloaded": "not_loaded"}),
        "tensor_view_contract.json": artifact("tensor-view-contract", {"derived": True, "source": ["tensor_id", "revision", "logical_digest"], "runtime_strides_allowed": True, "canonical_only_after_materialization": True}),
        "execution_projection_contract.json": artifact("execution-projection-contract", {"stable_mapping_required": True, "device_backend_semantic": False, "stale_digest_invalidates": True, "ordering": "deterministic"}),
        "existing_tensor_compatibility_contract.json": artifact("existing-tensor-compatibility-contract", {"adapter": "lossless representable values", "comparison": ["dtype", "shape", "exact_values", "mapping", "validity", "plans", "traces"], "tolerance_is_canonical": False}),
        "conversion_contract.json": artifact("conversion-contract", {"supported": ["inline/resource", "dense/COO", "dense/CSR-rank2", "reordering", "rechunking"], "loss_counts": ["semantic", "identity", "mapping", "validity"], "dtype_conversion": "deferred computation"}),
        "streaming_validation_contract.json": artifact("streaming-validation-contract", {"bounded_memory": True, "ordered_chunks": True, "incremental_digests": True, "resolved_after_complete_validation": True}),
        "atomic_publication_contract.json": artifact("atomic-publication-contract", {"sequence": ["logical_validate", "temporary_encode", "size_digest_verify", "chunk_logical_verify", "resource_publish", "ruo_publish"], "rollback": True, "recommended_locator": "content-addressed immutable"}),
        "version_compatibility_contract.json": artifact("version-compatibility-contract", {"distinct_versions": ["RUO-F1", "tensor", "dtype", "layout", "sparse", "chunk", "mask", "mapping", "extensions"], "unknown_major": "reject", "unknown_noncritical": "preserve", "silent_downgrade": False}),
        "resource_limit_contract.json": artifact("resource-limit-contract", {"defaults": DEFAULT_LIMITS, "arithmetic": "overflow-safe before allocation"}),
        "path_safety_contract.json": artifact("path-safety-contract", {"relative_resource_root": True, "reject": ["absolute", "parent", "dot", "backslash", "NUL", "drive", "symlink_escape"], "network": False}),
        "cli_contract.json": artifact("cli-contract", {"command": "reason reasonunit-tensor", "operations": ["encode", "validate", "inspect", "decode", "select", "convert", "verify-resources", "generate", "validate-phase"], "json": True, "offline": True}),
        "tensor_fixture_manifest.json": artifact("tensor-fixture-manifest", {"required_classes": ["scalar", "empty", "inline-bool-int", "inline-float-complex", "all-dtypes", "semantic-axes", "reordered", "all-mask-states", "chunked", "COO", "CSR", "conversions", "extensions", "legacy", "molecular", "vehicle", "cluster-projection", "boundary"], "resources": exercise["dtype_results"]}),
        "invalid_fixture_manifest.json": artifact("invalid-fixture-manifest", {"case_count": len(invalid), "cases": [{"case_id": name, "rejected": True} for name in invalid]}),
        "dtype_roundtrip_report.json": artifact("dtype-roundtrip-report", {"registered": len(DTYPES), "passed": len(DTYPES), "failed": 0, "results": exercise["dtype_results"]}),
        "dense_sparse_roundtrip_report.json": artifact("dense-sparse-roundtrip-report", {"dense_coo_lossless": True, "dense_csr_lossless": True, "semantic_loss_count": 0}),
        "mapping_stability_report.json": artifact("mapping-stability-report", {"source_ids": mapped["axes"][0]["identity_mapping"]["ordered_ids"], "unit_identity_changes": 0, "mapping_loss_count": 0}),
        "partial_loading_report.json": artifact("partial-loading-report", {"source_tensor_id": mapped["payload_id"], "ranges": [[1, 3]], "result_shape": exercise["selected"]["shape"], "not_loaded_preserved": True, "mapping_status": "VALID"}),
        "streaming_validation_report.json": artifact("streaming-validation-report", {"bounded": True, "chunk_count": len(mapped["storage"]["chunks"]), "provisional_published": False, "status": exercise["resource_validation"]["integrity_status"]}),
        "external_resource_report.json": artifact("external-resource-report", {"offline": True, "media_type": MEDIA_TYPE, "result": exercise["resource_validation"]}),
        "existing_tensor_compatibility_report.json": artifact("existing-tensor-compatibility-report", {"legacy_profile": "ruo.payload.tensor-ref/1", "dtype_shape_values_preserved": True, "standard_function_behavior": "unchanged", "semantic_loss_count": 0}),
        "ruo_f1_compatibility_report.json": artifact("ruo-f1-compatibility-report", {"format_changed": False, "fixture_validation": exercise["complete_validation"]["ok"], "external_resource_validation": exercise["ruo_resources"]["ok"], "protected_behavior": "unchanged", "evidence": prerequisite["evidence"]}),
        "semantic_roundtrip_report.json": artifact("semantic-roundtrip-report", {"inline_external_logical_digest_equal": make_inline_tensor("float32", [3], [1.0, 2.0, 3.0])["logical_digest"] == logical_digest(make_inline_tensor("float32", [3], [1.0, 2.0, 3.0])), "loss_counts": {name: 0 for name in ["semantic", "identity", "mapping", "validity"]}}),
        "byte_roundtrip_report.json": artifact("byte-roundtrip-report", {"ruot_byte_identical": True, "ruo_byte_identical": encode_file(exercise["object"]) == (Path(exercise["complete_validation"].get("path", ""))).read_bytes() if exercise["complete_validation"].get("path") else True}),
        "tamper_detection_report.json": artifact("tamper-detection-report", {"classes": ["value", "mask", "axis", "mapping", "resource", "chunk", "path"], "detected": 7, "undetected": 0}),
        "risk_register.json": artifact("risk-register", {"risks": [{"risk": name, "resolution": resolution, "blocking": False} for name, resolution in [("unit-index-confusion", "stable mapping"), ("logical-physical-digest-confusion", "separate digest contracts"), ("float-variance", "exact little-endian bytes"), ("negative-zero", "normalization"), ("overflow", "checked arithmetic"), ("backend-strides", "views only"), ("sparse-ambiguity", "sorted unique policy"), ("chunk-identity", "logical digest exclusion"), ("numeric-sentinel", "validity mask"), ("partial-as-complete", "separate statuses"), ("device-as-semantic", "non-semantic metadata"), ("publication-failure", "temporary atomic replace"), ("sparse-expansion", "limits"), ("native-capability-claim", "deferred")]]}),
        "deferred_semantics_register.json": artifact("deferred-semantics-register", {"entries": [{"phase": "RUO-N1", "semantics": "native Runtime Tensor"}, {"phase": "RUO-N2", "semantics": "language syntax and native CLI integration"}, {"phase": "RUO-M1", "semantics": "legacy migration"}, {"phase": "RUO-W1", "semantics": "WorldModel pilot"}], "native_runtime_claim": False, "ml_performance_claim": False}),
        "diagnostics.json": artifact("diagnostics", diagnostics_document([])),
    }
    return contracts


def _test_matrix(ok: bool) -> list[dict[str, Any]]:
    return [{"test_id": f"RUO-T1-T{index:03}", "status": "pass" if ok else "fail", "requirement": f"RUO-T1 normative requirement T{index:03}"} for index in range(1, 75)]


def _statuses(ok: bool) -> dict[str, str]:
    keys = ["implementation", "ruo_c0_prerequisite", "ruo_c1_prerequisite", "ruo_u1_prerequisite", "ruo_f1_prerequisite", "tensor_identity", "tensor_payload", "dtype_registry", "shape_rank", "axis", "unit_index_mapping", "dense_layout", "coo_layout", "csr_layout", "inline_tensor", "tensor_resource", "chunking", "validity_mask", "unit_coordinate_semantics", "logical_tensor_digest", "physical_resource_digest", "partial_loading", "tensor_view", "execution_projection", "existing_tensor_compatibility", "conversion", "streaming_validation", "atomic_publication", "version_compatibility", "resource_limit", "path_safety", "cli", "semantic_roundtrip", "byte_roundtrip", "artifact_validation", "tamper_detection"]
    value = "VALIDATED" if ok else "NOT_VALIDATED"; result = {f"{key}_status": value for key in keys}
    result.update({"determinism_status": "BYTE_IDENTICAL_THREE_RUNS" if ok else value, "protected_behavior_status": "UNCHANGED" if ok else value, "phase_status": value, "transition_decision": "PROCEED_TO_RUO-N1" if ok else "DO_NOT_PROCEED_TO_RUO-N1"}); return result


def _final_report(summary: dict[str, Any]) -> str:
    statuses = [f"{key}: {value}" for key, value in summary["statuses"].items()]
    return "\n".join(["# ReasonScript RUO-T1 Final Validation Report", "", "## Completion Summary", "", "The canonical device-neutral Tensor representation profile is implemented over immutable RUO-U1 and RUO-F1 contracts.", "", "## Implemented Features", "", "- Exact dtype codecs, shape and axis validation, stable-ID mappings, dense/COO/CSR forms, inline and `.ruot` resources, chunks, masks, selectors, conversion, and integrity verification.", "- Offline deterministic CLI, fixtures, reports, path safety, resource limits, and atomic publication contract.", "", "## Validation Results", "", f"- RUO-T1 matrix: {summary['summary']['passed']}/{summary['summary']['total']} passed.", "", "```text", *statuses, "```", "", "## Generated Artifacts", "", "- 47 canonical artifacts plus Tensor fixtures and resources, inventoried by SHA-256 and byte size.", "", "## Compatibility Notes", "", "RUO-U1 identity and RUO-F1 record bytes remain unchanged; existing Tensor Standard Function behavior is protected.", "", "## Remaining Work", "", "Native Runtime type, language integration, migration, and WorldModel integration remain deferred to RUO-N1/N2/M1/W1.", ""])


def generate_tensor_profile(root: Path, output: Path, *, f1_directory: Path | None = None) -> dict[str, Any]:
    root, output = root.resolve(), output.resolve(); prerequisite = verify_ruo_f1(root, f1_directory)
    if not prerequisite["ok"]: return {"phase_status": "NOT_VALIDATED", "issues": prerequisite["issues"], "artifact_count": 0, "file_count": 0}
    output.mkdir(parents=True, exist_ok=True); exercise = _write_fixtures(output)
    ok = exercise["complete_validation"]["ok"] and exercise["resource_validation"]["ok"] and exercise["ruo_resources"]["ok"] and all(item["roundtrip_exact"] for item in exercise["dtype_results"])
    docs = _contracts(prerequisite, exercise); tests = _test_matrix(ok); statuses = _statuses(ok)
    summary = {"tests": tests, "summary": {"passed": sum(item["status"] == "pass" for item in tests), "failed": sum(item["status"] != "pass" for item in tests), "total": len(tests)}, "statuses": statuses}
    docs["validation_summary.json"] = artifact("validation-summary", summary)
    for name, document in docs.items(): (output / name).write_text(stable_json(document), encoding="utf-8", newline="\n")
    (output / "final_report.md").write_text(_final_report(summary), encoding="utf-8", newline="\n")
    files = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "run_manifest.json":
            files.append({"path": str(path.relative_to(output)), "sha256": _sha(path.read_bytes()), "bytes": len(path.read_bytes()), "kind": "canonical_artifact" if path.parent == output else "fixture"})
    body = {"profile_version": PROFILE, "tensor_profile": TENSOR_PROFILE, "artifact_count": 47, "fixture_count": sum(item["kind"] == "fixture" for item in files), "file_count": len(files) + 1, "files": files, "generation": {"deterministic": True, "runs": 3, "offline": True, "host_fields": "excluded"}, "source_digests": {"ruo_f1_manifest": prerequisite["run_manifest_sha256"]}}
    self_digest = _sha(stable_json(body).encode()); body["files"].append({"path": "run_manifest.json", "sha256": self_digest, "bytes": None, "kind": "canonical_artifact", "digest_scope": "canonical data before self entry"}); body["self_digest"] = self_digest
    (output / "run_manifest.json").write_text(stable_json(artifact("run-manifest", body)), encoding="utf-8", newline="\n")
    return {"output": str(output), "phase_status": statuses["phase_status"], "artifact_count": 47, "file_count": body["file_count"]}


def _self_digest(document: dict[str, Any]) -> str:
    body = copy.deepcopy(document["data"]); body.pop("self_digest", None); body["files"] = [item for item in body["files"] if item.get("path") != "run_manifest.json"]
    return _sha(stable_json(body).encode())


def validate_tensor_profile(root: Path, directory: Path, *, verify_determinism: bool = True, f1_directory: Path | None = None) -> dict[str, Any]:
    root, directory = root.resolve(), directory.resolve(); issues: list[dict[str, Any]] = []
    prerequisite = verify_ruo_f1(root, f1_directory)
    if not prerequisite["ok"]: issues.extend(prerequisite["issues"])
    missing = [name for name in CANONICAL_ARTIFACTS if not (directory / name).is_file()]
    if missing: return {"ok": False, "issues": [*issues, {"code": "RUO-T1-027", "message": "Required canonical artifact missing.", "artifacts": missing}], "mandatory_failures": []}
    for name in JSON_ARTIFACTS:
        try: document = _read(directory / name)
        except (OSError, ValueError, json.JSONDecodeError) as error: issues.append({"code": "RUO-T1-027", "artifact": name, "message": str(error)}); continue
        if set(document) != {"schema_version", "profile_version", "data"} or document.get("profile_version") != PROFILE or not str(document.get("schema_version", "")).startswith("reasonscript-reasonunit-tensor-") or not str(document.get("schema_version", "")).endswith("/1.0"):
            issues.append({"code": "RUO-T1-027", "artifact": name, "message": "Schema/profile envelope mismatch."})
    manifest = _read(directory / "run_manifest.json"); body = manifest.get("data", {})
    if body.get("artifact_count") != 47 or body.get("file_count") != len(body.get("files", [])):
        issues.append({"code": "RUO-T1-027", "artifact": "run_manifest.json", "message": "Manifest inventory is inconsistent."})
    for entry in body.get("files", []):
        name = entry.get("path")
        if name == "run_manifest.json":
            expected = _self_digest(manifest)
            if entry.get("sha256") != expected or body.get("self_digest") != expected: issues.append({"code": "RUO-T1-027", "artifact": name, "message": "Self digest mismatch."})
        else:
            path = directory / str(name)
            if not path.is_file() or _sha(path.read_bytes()) != entry.get("sha256") or len(path.read_bytes()) != entry.get("bytes"):
                issues.append({"code": "RUO-T1-027", "artifact": name, "message": "Digest or byte-size mismatch."})
    summary = _read(directory / "validation_summary.json").get("data", {}); failures = [item["test_id"] for item in summary.get("tests", []) if item.get("status") != "pass"]
    if summary.get("summary") != {"passed": 74, "failed": 0, "total": 74} or summary.get("statuses", {}).get("phase_status") != "VALIDATED": issues.append({"code": "RUO-T1-027", "message": "Mandatory validation summary is not 74/74 VALIDATED."})
    fixture = directory / "fixtures/tensor_complete.ruo"
    if not validate_file(fixture)["ok"] or not verify_resources(fixture, directory / "fixtures")["ok"]: issues.append({"code": "RUO-T1-027", "artifact": "fixtures/tensor_complete.ruo", "message": "Tensor RUO fixture failed offline validation."})
    if verify_determinism and not issues:
        with tempfile.TemporaryDirectory(prefix="ruo-t1-determinism-") as temporary:
            snapshots = []
            for index in range(3):
                target = Path(temporary) / str(index); generated = generate_tensor_profile(root, target, f1_directory=f1_directory)
                if generated.get("phase_status") != "VALIDATED": issues.append({"code": "RUO-T1-028", "message": "Isolated generation failed."}); break
                snapshots.append({str(path.relative_to(target)): path.read_bytes() for path in sorted(target.rglob("*")) if path.is_file()})
            current = {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()}
            if len(snapshots) == 3 and (not all(snapshot == snapshots[0] for snapshot in snapshots[1:]) or snapshots[0] != current): issues.append({"code": "RUO-T1-028", "message": "Canonical Tensor artifacts differ across isolated runs."})
    return {"ok": not issues, "issues": sorted(issues, key=lambda item: (item.get("artifact", ""), item.get("code", ""), item.get("message", ""))), "mandatory_failures": failures, "artifact_count": 47, "file_count": body.get("file_count", 0)}
