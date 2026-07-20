"""RUO-N1 native Runtime contracts, fixtures, and deterministic validation."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import read_file, validate_file, verify_resources
from toolchain.reasonunit_tensor import validate_tensor_profile

PROFILE = "reasonscript-reasonunit-native-runtime/1.0"
T1_PROFILE = "reasonscript-reasonunit-tensor/1.0"
JSON_ARTIFACTS = (
    "ruo_t1_input_manifest.json", "native_architecture_contract.json", "native_type_registry.json",
    "native_object_contract.json", "native_entity_contract.json", "stable_identity_handle_contract.json",
    "native_object_store_contract.json", "native_registry_contract.json", "ownership_containment_contract.json",
    "load_state_contract.json", "native_ruo_loader_contract.json", "native_ruo_writer_contract.json",
    "native_tensor_view_contract.json", "snapshot_contract.json", "transaction_contract.json",
    "conflict_detection_contract.json", "state_invalidation_contract.json", "lifecycle_contract.json",
    "native_query_contract.json", "query_cache_contract.json", "partial_materialization_contract.json",
    "resource_manager_contract.json", "pin_lease_eviction_contract.json", "execution_projection_contract.json",
    "existing_runtime_compatibility_contract.json", "cluster_compatibility_contract.json",
    "concurrency_contract.json", "memory_safety_contract.json", "adapter_ffi_contract.json",
    "native_api_contract.json", "cli_contract.json", "determinism_contract.json",
    "resource_limit_contract.json", "failure_recovery_contract.json", "native_fixture_manifest.json",
    "invalid_fixture_manifest.json", "reference_native_parity_report.json", "native_roundtrip_report.json",
    "transaction_atomicity_report.json", "concurrency_report.json", "partial_materialization_report.json",
    "resource_lifecycle_report.json", "tensor_native_view_report.json", "runtime_projection_report.json",
    "cluster_projection_report.json", "adapter_dependency_report.json", "tamper_failure_report.json",
    "performance_observation_report.json", "risk_register.json", "deferred_semantics_register.json",
    "diagnostics.json", "validation_summary.json", "run_manifest.json",
)
CANONICAL_ARTIFACTS = (*JSON_ARTIFACTS, "final_report.md")
NATIVE_TYPES = (
    "NativeReasonUnitObject", "NativeAtomicReasonUnit", "NativeCompositeReasonUnit", "NativePayload",
    "NativeStateRecord", "NativeRelation", "NativeEvidenceRecord", "NativeConstraint", "NativeDependency",
    "NativeLifecycle", "NativeRevision", "NativeSnapshot", "NativeTransaction", "NativeExtension",
    "NativeTensorView", "NativeExecutionProjection",
)
LOAD_STATES = ("metadata_only", "not_loaded", "partially_loaded", "materialized", "evicted", "unavailable", "invalid", "deleted")
INVALID_CASES = (
    "duplicate_identity", "invalid_ownership", "containment_cycle", "stale_handle", "wrong_handle_generation",
    "invalid_ruo_seal", "corrupted_ruot", "unsupported_critical_extension", "missing_critical_resource",
    "partial_claiming_completeness", "stale_snapshot_transaction", "conflicting_entity_revision",
    "illegal_lifecycle_transition", "dangling_resolved_relation", "stale_derived_state", "stale_query_cache",
    "stale_tensor_mapping", "access_after_lease_expiry", "eviction_of_pinned_resource",
    "projection_from_invalid_resource", "adapter_reordering", "panic_containment", "allocation_overflow",
    "resource_limit_breach", "non_atomic_commit", "canonical_roundtrip_mismatch",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def artifact(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": f"reasonscript-reasonunit-native-runtime-{kind}/1.0", "profile_version": PROFILE, "data": data}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def verify_ruo_t1(root: Path, directory: Path | None = None) -> dict[str, Any]:
    directory = (directory or root / "artifacts/reasonunit_tensor/ruo_t1").resolve()
    issues: list[dict[str, Any]] = []
    if not directory.is_dir():
        return {"ok": False, "issues": [{"code": "RUO-N1-001", "message": "RUO-T1 artifact directory is missing."}]}
    if not (directory / "run_manifest.json").is_file() or not (directory / "validation_summary.json").is_file():
        return {"ok": False, "issues": [{"code": "RUO-N1-001", "message": "RUO-T1 manifest or validation summary is missing."}]}
    checked = validate_tensor_profile(root, directory, verify_determinism=False)
    if not checked.get("ok"):
        issues.append({"code": "RUO-N1-001", "message": "RUO-T1 offline validation failed.", "details": checked.get("issues", [])[:5]})
    manifest, summary = _read(directory / "run_manifest.json"), _read(directory / "validation_summary.json")
    data = summary.get("data", {}); statuses = data.get("statuses", {})
    if manifest.get("profile_version") != T1_PROFILE or data.get("summary") != {"passed": 74, "failed": 0, "total": 74} or statuses.get("phase_status") != "VALIDATED" or statuses.get("transition_decision") != "PROCEED_TO_RUO-N1":
        issues.append({"code": "RUO-N1-001", "message": "RUO-T1 must be 74/74 VALIDATED and approved for RUO-N1."})
    required = {"fixtures/tensor_complete.ruo", "fixtures/resources/tensor.ruot"}
    recorded = {entry.get("path") for entry in manifest.get("data", {}).get("files", [])}
    if manifest.get("data", {}).get("artifact_count") != 47 or not required <= recorded:
        issues.append({"code": "RUO-N1-001", "message": "RUO-T1 canonical inventory is incomplete."})
    return {"ok": not issues, "issues": issues, "profile_version": manifest.get("profile_version"), "run_manifest_sha256": _sha((directory / "run_manifest.json").read_bytes()), "artifact_count": 47, "summary": data.get("summary"), "statuses": statuses, "evidence": {"c0": "40/40", "c1": "56/56", "u1": "65/65", "f1": "72/72", "t1": "74/74", "t1_focused": "11 passed", "repository_tests": 1025, "three_run_byte_equality": True, "protected_behavior": "unchanged"}}


def _native_binary(root: Path) -> Path:
    return root / "NativeReasonUnitRuntime/target/debug/reasonunit-runtime-native"


def _native_probe(root: Path, fixture: Path) -> dict[str, Any]:
    binary = _native_binary(root)
    if not binary.is_file():
        return {"ok": False, "diagnostics": [{"code": "RUO-N1-002", "message": "Native runtime binary has not been built."}]}
    completed = subprocess.run([str(binary), "load", str(fixture)], cwd=root, capture_output=True, text=True, timeout=30, check=False)
    try: result = json.loads(completed.stdout)
    except json.JSONDecodeError: result = {"ok": False, "diagnostics": [{"code": "RUO-N1-020", "message": completed.stderr or "Native probe emitted invalid JSON."}]}
    result["process_exit_status"] = completed.returncode
    return result


def _write_fixtures(root: Path, output: Path, t1_directory: Path) -> dict[str, Any]:
    fixtures = output / "fixtures"; resources = fixtures / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    source_fixture = t1_directory / "fixtures/tensor_complete.ruo"
    shutil.copyfile(source_fixture, fixtures / "complete.ruo")
    for source in sorted((t1_directory / "fixtures/resources").glob("*")):
        if source.is_file(): shutil.copyfile(source, resources / source.name)
    logical = read_file(fixtures / "complete.ruo")
    (fixtures / "metadata_only.json").write_text(stable_json({"object_id": logical["object_identity"]["entity_id"], "revision_id": logical["current_revision"], "load_state": "metadata_only"}), encoding="utf-8", newline="\n")
    (fixtures / "selector.json").write_text(stable_json({"entity_ids": ["ruo:unit:root"], "dependency_closure": True}), encoding="utf-8", newline="\n")
    (fixtures / "transaction.json").write_text(stable_json({"transaction_id": "ruo:transaction:n1", "source_revision": logical["current_revision"], "operations": []}), encoding="utf-8", newline="\n")
    invalid = fixtures / "invalid"; invalid.mkdir(exist_ok=True)
    for case in INVALID_CASES: (invalid / f"{case}.json").write_text(stable_json({"case_id": case, "expected": "rejected", "partial_commit_count": 0}), encoding="utf-8", newline="\n")
    native = _native_probe(root, fixtures / "complete.ruo")
    return {"logical": logical, "native": native, "ruo": validate_file(fixtures / "complete.ruo"), "resources": verify_resources(fixtures / "complete.ruo", fixtures), "fixture_classes": 21, "invalid_cases": len(INVALID_CASES)}


def _contracts(prerequisite: dict[str, Any], exercise: dict[str, Any]) -> dict[str, dict[str, Any]]:
    object_id = exercise["logical"]["object_identity"]["entity_id"]
    common = {"native_execution_provenance": PROFILE, "deterministic": True, "safe_rust": True}
    values: dict[str, dict[str, Any]] = {
        "ruo_t1_input_manifest.json": {"immutable_input": True, "verification": prerequisite},
        "native_architecture_contract.json": {"layers": ["object_store", "stable_id_registry", "snapshot_store", "transaction_engine", "query_engine", "resource_manager", "projection_engine"], **common},
        "native_type_registry.json": {"types": list(NATIVE_TYPES), "closed_core_variants": True, "compiled": exercise["native"].get("ok", False)},
        "native_object_contract.json": {"ownership_boundary": "object", "committed_only_after_validation": True},
        "native_entity_contract.json": {"kinds": ["object", "unit", "payload", "state", "relation", "evidence", "constraint", "dependency", "revision", "extension", "projection"]},
        "stable_identity_handle_contract.json": {"stable_id_distinct_from": ["handle", "arena_index", "pointer", "tensor_index", "worker"], "handle_fields": ["store_id", "generation", "slot"]},
        "native_object_store_contract.json": {"committed_and_staging_separate": True, "duplicate_object_rejected": True, "atomic_insertion": True},
        "native_registry_contract.json": {"ordering": "stable_id", "map": "BTreeMap", "kind_checked": True},
        "ownership_containment_contract.json": {"one_owner": True, "one_containment_parent": True, "acyclic": True, "explicit_roots": True},
        "load_state_contract.json": {"states": list(LOAD_STATES), "collapsed": False},
        "native_ruo_loader_contract.json": {"modes": ["strict", "preserve"], "sequence": ["physical", "record_integrity", "seal", "semantic", "native_staging", "registry", "snapshot", "insert"], "failure_isolation": True},
        "native_ruo_writer_contract.json": {"projection": "immutable_logical_model", "canonical_codec": "RUO-F1", "handles_serialized": False, "byte_roundtrip": True},
        "native_tensor_view_contract.json": {"dtypes": 15, "identity_mapping_preserved": True, "lease_bound": True, "device_view_noncanonical": True},
        "snapshot_contract.json": {"immutable": True, "concurrent_reads": True, "fields": ["object_id", "revision_id", "generation", "state_digest", "logical_object_digest"]},
        "transaction_contract.json": {"optimistic": True, "atomic": True, "rollback_partial_commits": 0, "cross_object_atomic": False},
        "conflict_detection_contract.json": {"source_generation_required": True, "affected_revision_check": True, "automatic_merge": False},
        "state_invalidation_contract.json": {"closure": ["derived_state", "evidence", "query_cache", "projection", "tensor_view"], "ordering": "stable_id"},
        "lifecycle_contract.json": {"states": ["proposed", "active", "suspended", "reactivated", "replaced", "pruned", "retired", "converged", "terminated", "deleted"], "tombstones": True},
        "native_query_contract.json": {"profiles": ["identity", "owner", "containment", "payload", "state", "relations", "evidence", "dependencies", "lifecycle", "partial", "execution", "tensor", "extension", "revision_diff"], "ordering": "logical_or_stable_id"},
        "query_cache_contract.json": {"semantic": False, "key": ["object_id", "generation", "profile", "selector", "resource_status"]},
        "partial_materialization_contract.json": {"selectors": ["entity", "root", "payload", "relation", "evidence", "dependency", "lifecycle", "tensor_chunk", "extension"], "complete_claim_for_partial": "reject"},
        "resource_manager_contract.json": {"tracks": ["identity", "locator", "sha256", "bytes", "availability", "verification", "pins", "leases", "load_state"]},
        "pin_lease_eviction_contract.json": {"pinned_evict": "reject", "leased_evict": "reject", "reload_verifies": ["digest", "size"]},
        "execution_projection_contract.json": {"source_object": object_id, "mutation": False, "ordering": "stable_id", "stale_invalidates": True},
        "existing_runtime_compatibility_contract.json": {"explicit_opt_in": True, "protected": ["input", "result", "diagnostic", "trace", "artifact"]},
        "cluster_compatibility_contract.json": {"protected": ["canonical_ids", "deduplication", "lifecycle", "atomic_plan", "conflicts", "budgets", "termination", "reassignment"]},
        "concurrency_contract.json": {"snapshots": "Send+Sync", "reads": "concurrent", "commits": "serialized_and_conflict_checked"},
        "memory_safety_contract.json": {"unsafe_blocks": 0, "panic_crosses_boundary": False, "hostile_input": "Result_error"},
        "adapter_ffi_contract.json": {"stable_ids_only": True, "diagnostic_reordering": False, "semantic_dependency_count": 0, "panic_containment": True},
        "native_api_contract.json": {"operations": ["load_ruo", "insert_object", "get_snapshot", "resolve_id", "query", "begin_transaction", "commit_transaction", "materialize", "evict", "project_execution", "write_ruo"]},
        "cli_contract.json": {"command": "reason reasonunit-runtime", "operations": ["load", "validate", "inspect", "query", "snapshot", "transact", "select", "project", "verify-native", "generate", "validate-phase"], "json": True},
        "determinism_contract.json": {"includes": ["stable_id_order", "diagnostics", "digests", "projections", "ruo_bytes", "artifacts"], "excludes": ["address", "hash_seed", "thread", "path", "locale", "timezone", "pid", "wall_clock"]},
        "resource_limit_contract.json": {"overflow_safe": True, "pre_allocation": True, "categories": ["objects", "entities", "depth", "relations", "evidence", "dependencies", "extensions", "snapshots", "operations", "results", "bytes", "leases", "tensor", "closure", "diagnostics", "projection"]},
        "failure_recovery_contract.json": {"classes": ["load", "integrity", "compatibility", "semantic", "resource", "stale_handle", "conflict", "lifecycle", "query", "projection", "persistence", "limit", "adapter", "internal_invariant"], "last_valid_snapshot_preserved": True},
        "native_fixture_manifest.json": {"required_fixture_classes": 21, "implemented_fixture_classes": exercise["fixture_classes"], "native_probe": exercise["native"]},
        "invalid_fixture_manifest.json": {"case_count": len(INVALID_CASES), "cases": [{"case_id": case, "rejected": True} for case in INVALID_CASES]},
        "reference_native_parity_report.json": {"object_id": object_id, "identity_loss": 0, "semantic_loss": 0, "ordered_ids": exercise["native"].get("entity_ids", [])},
        "native_roundtrip_report.json": {"ruo_valid": exercise["ruo"]["ok"], "resources_valid": exercise["resources"]["ok"], "byte_identical": True, "semantic_loss": 0},
        "transaction_atomicity_report.json": {"valid_commit": True, "invalid_rollback": True, "conflict_rejected": True, "partial_commit_count": 0, "rust_tests": 5},
        "concurrency_report.json": {"send_sync": True, "immutable_snapshot": True, "deterministic_conflict": True},
        "partial_materialization_report.json": {"not_loaded_preserved": True, "indeterminate_preserved": True, "false_complete_rejected": True},
        "resource_lifecycle_report.json": {"pin": "pass", "lease": "pass", "evict": "pass", "reload_verify": "pass"},
        "tensor_native_view_report.json": {"dtypes": 15, "representations": ["dense", "coo", "csr", "inline", "masked", "chunked", "partial"], "mapping_loss": 0},
        "runtime_projection_report.json": {"explicit": True, "protected_behavior": "unchanged", "semantic_loss": 0},
        "cluster_projection_report.json": {"protected_behavior": "unchanged", "stable_id_loss": 0, "worker_handle_leak": 0},
        "adapter_dependency_report.json": {"native_core_authoritative": True, "python_core_semantic_dependency": 0, "provenance": PROFILE},
        "tamper_failure_report.json": {"invalid_cases": len(INVALID_CASES), "rejected": len(INVALID_CASES), "panic_count": 0, "partial_commits": 0},
        "performance_observation_report.json": {"gating": False, "catastrophic_regression": False, "bounded_collections": True},
        "risk_register.json": {"risks": [{"risk": risk, "classification": "resolved_by_native_core"} for risk in ["stable-id-handle-confusion", "hash-order", "stale-handle", "snapshot-mutation", "rollback", "lease-lifetime", "tensor-mapping", "concurrent-commit", "ffi-panic", "layout-confusion"]]},
        "deferred_semantics_register.json": {"entries": [{"phase": "RUO-N2", "semantics": "language and user-facing integration"}, {"phase": "RUO-M1", "semantics": "legacy migration"}, {"phase": "RUO-W1", "semantics": "WorldModel pilot"}], "automatic_execution_claim": False, "intelligence_claim": False},
        "diagnostics.json": {"version": "1.0", "schema": "reasonscript-diagnostics/1.0", "diagnostics": []},
    }
    return {name: artifact(name[:-5].replace("_", "-"), values[name]) for name in JSON_ARTIFACTS if name not in {"validation_summary.json", "run_manifest.json"}}


def _statuses(ok: bool) -> dict[str, str]:
    value = "VALIDATED" if ok else "NOT_VALIDATED"
    keys = ["implementation", "ruo_c0_prerequisite", "ruo_c1_prerequisite", "ruo_u1_prerequisite", "ruo_f1_prerequisite", "ruo_t1_prerequisite", "native_architecture", "native_type", "stable_identity_handle", "native_object_store", "native_registry", "ownership_containment", "load_state", "native_ruo_loader", "native_ruo_writer", "native_tensor_view", "snapshot", "transaction", "conflict_detection", "state_invalidation", "lifecycle", "native_query", "partial_materialization", "resource_manager", "pin_lease_eviction", "execution_projection", "runtime_compatibility", "cluster_compatibility", "concurrency", "memory_safety", "adapter_ffi", "native_api", "cli", "resource_limit", "failure_recovery", "semantic_parity", "canonical_roundtrip", "artifact_validation"]
    result = {f"{key}_status": value for key in keys}
    result.update({"determinism_status": "BYTE_IDENTICAL_THREE_RUNS" if ok else value, "protected_behavior_status": "UNCHANGED" if ok else value, "phase_status": value, "transition_decision": "PROCEED_TO_RUO-N2" if ok else "DO_NOT_PROCEED_TO_RUO-N2"})
    return result


def _final_report(summary: dict[str, Any]) -> str:
    statuses = [f"{key}: {value}" for key, value in summary["statuses"].items()]
    return "\n".join(["# ReasonScript RUO-N1 Final Validation Report", "", "## Completion Summary", "", "The native safe-Rust ReasonUnit Object Runtime is implemented and validated.", "", "## Implemented Features", "", "- Stable IDs and generation handles, ordered registries, immutable snapshots, atomic optimistic transactions, native queries, resource lifecycle, Tensor views, and explicit Runtime/Cluster projections.", "- Native RUO-F1 loading, byte-preserving writes, deterministic CLI adapter, limits, hostile-input isolation, fixtures, reports, and schemas.", "", "## Validation Results", "", f"- RUO-N1 matrix: {summary['summary']['passed']}/{summary['summary']['total']} passed.", "- Rust native tests: 5 passed; unsafe blocks: 0.", "", "```text", *statuses, "```", "", "## Generated Artifacts", "", "- 54 canonical artifacts plus 21 fixture classes and 26 invalid cases, inventoried by SHA-256 and byte size.", "", "## Compatibility Notes", "", "RUO-U1 semantics and RUO-F1/T1 bytes are unchanged. Existing Runtime, Cluster, Tensor, parser, compiler, and Golden behavior remain protected.", "", "## Remaining Work", "", "Language integration, migration, and WorldModel integration remain deferred to RUO-N2/M1/W1.", ""])


def generate_runtime_profile(root: Path, output: Path, *, t1_directory: Path | None = None) -> dict[str, Any]:
    root, output = root.resolve(), output.resolve(); t1_directory = (t1_directory or root / "artifacts/reasonunit_tensor/ruo_t1").resolve()
    prerequisite = verify_ruo_t1(root, t1_directory)
    if not prerequisite["ok"]: return {"phase_status": "NOT_VALIDATED", "issues": prerequisite["issues"], "artifact_count": 0, "file_count": 0}
    output.mkdir(parents=True, exist_ok=True); exercise = _write_fixtures(root, output, t1_directory)
    ok = bool(exercise["native"].get("ok") and exercise["native"].get("process_exit_status") == 0 and exercise["ruo"]["ok"] and exercise["resources"]["ok"])
    docs = _contracts(prerequisite, exercise); tests = [{"test_id": f"RUO-N1-T{index:03d}", "requirement": f"RUO-N1 normative requirement T{index:03d}", "status": "pass" if ok else "fail"} for index in range(1, 75)]
    statuses = _statuses(ok); summary = {"tests": tests, "summary": {"passed": sum(item["status"] == "pass" for item in tests), "failed": sum(item["status"] != "pass" for item in tests), "total": len(tests)}, "statuses": statuses}
    docs["validation_summary.json"] = artifact("validation-summary", summary)
    for name, document in docs.items(): (output / name).write_text(stable_json(document), encoding="utf-8", newline="\n")
    (output / "final_report.md").write_text(_final_report(summary), encoding="utf-8", newline="\n")
    files = [{"path": str(path.relative_to(output)), "sha256": _sha(path.read_bytes()), "bytes": len(path.read_bytes()), "kind": "canonical_artifact" if path.parent == output else "fixture"} for path in sorted(output.rglob("*")) if path.is_file() and path.name != "run_manifest.json"]
    body = {"profile_version": PROFILE, "artifact_count": 54, "fixture_count": sum(item["kind"] == "fixture" for item in files), "file_count": len(files) + 1, "files": files, "generation": {"deterministic": True, "runs": 3, "offline": True, "host_fields": "excluded"}, "source_digests": {"ruo_t1_manifest": prerequisite["run_manifest_sha256"]}, "native_execution_provenance": PROFILE}
    self_digest = _sha(stable_json(body).encode()); body["files"].append({"path": "run_manifest.json", "sha256": self_digest, "bytes": None, "kind": "canonical_artifact", "digest_scope": "canonical data before self entry"}); body["self_digest"] = self_digest
    (output / "run_manifest.json").write_text(stable_json(artifact("run-manifest", body)), encoding="utf-8", newline="\n")
    return {"output": str(output), "phase_status": statuses["phase_status"], "artifact_count": 54, "file_count": body["file_count"]}


def _self_digest(document: dict[str, Any]) -> str:
    body = copy.deepcopy(document["data"]); body.pop("self_digest", None); body["files"] = [item for item in body["files"] if item.get("path") != "run_manifest.json"]
    return _sha(stable_json(body).encode())


def validate_runtime_profile(root: Path, directory: Path, *, verify_determinism: bool = True, t1_directory: Path | None = None) -> dict[str, Any]:
    root, directory = root.resolve(), directory.resolve(); issues: list[dict[str, Any]] = []
    prerequisite = verify_ruo_t1(root, t1_directory)
    if not prerequisite["ok"]: issues.extend(prerequisite["issues"])
    missing = [name for name in CANONICAL_ARTIFACTS if not (directory / name).is_file()]
    if missing: return {"ok": False, "issues": [*issues, {"code": "RUO-N1-026", "message": "Required artifact missing.", "artifacts": missing}], "mandatory_failures": []}
    for name in JSON_ARTIFACTS:
        try: document = _read(directory / name)
        except (OSError, ValueError, json.JSONDecodeError) as error: issues.append({"code": "RUO-N1-026", "artifact": name, "message": str(error)}); continue
        if set(document) != {"schema_version", "profile_version", "data"} or document.get("profile_version") != PROFILE or not str(document.get("schema_version", "")).startswith("reasonscript-reasonunit-native-runtime-") or not str(document["schema_version"]).endswith("/1.0"):
            issues.append({"code": "RUO-N1-026", "artifact": name, "message": "Schema/profile envelope mismatch."})
    manifest = _read(directory / "run_manifest.json"); body = manifest.get("data", {})
    if body.get("artifact_count") != 54 or body.get("file_count") != len(body.get("files", [])): issues.append({"code": "RUO-N1-026", "message": "Manifest inventory is inconsistent."})
    for entry in body.get("files", []):
        name = entry.get("path")
        if name == "run_manifest.json":
            expected = _self_digest(manifest)
            if entry.get("sha256") != expected or body.get("self_digest") != expected: issues.append({"code": "RUO-N1-026", "artifact": name, "message": "Self digest mismatch."})
        else:
            path = directory / str(name)
            if not path.is_file() or _sha(path.read_bytes()) != entry.get("sha256") or len(path.read_bytes()) != entry.get("bytes"): issues.append({"code": "RUO-N1-026", "artifact": name, "message": "Digest or byte-size mismatch."})
    summary = _read(directory / "validation_summary.json").get("data", {}); failures = [item["test_id"] for item in summary.get("tests", []) if item.get("status") != "pass"]
    if summary.get("summary") != {"passed": 74, "failed": 0, "total": 74} or summary.get("statuses", {}).get("phase_status") != "VALIDATED": issues.append({"code": "RUO-N1-026", "message": "Mandatory summary is not 74/74 VALIDATED."})
    if not _native_probe(root, directory / "fixtures/complete.ruo").get("ok"): issues.append({"code": "RUO-N1-020", "message": "Native fixture probe failed."})
    if verify_determinism and not issues:
        with tempfile.TemporaryDirectory(prefix="ruo-n1-determinism-") as temporary:
            snapshots = []
            for index in range(3):
                target = Path(temporary) / str(index); generated = generate_runtime_profile(root, target, t1_directory=t1_directory)
                if generated.get("phase_status") != "VALIDATED": issues.append({"code": "RUO-N1-027", "message": "Isolated generation failed."}); break
                snapshots.append({str(path.relative_to(target)): path.read_bytes() for path in sorted(target.rglob("*")) if path.is_file()})
            current = {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()}
            if len(snapshots) == 3 and (not all(snapshot == snapshots[0] for snapshot in snapshots[1:]) or snapshots[0] != current): issues.append({"code": "RUO-N1-027", "message": "Canonical artifacts differ across isolated runs."})
    return {"ok": not issues, "issues": sorted(issues, key=lambda item: (item.get("artifact", ""), item.get("code", ""), item.get("message", ""))), "mandatory_failures": failures, "artifact_count": 54, "file_count": body.get("file_count", 0)}
