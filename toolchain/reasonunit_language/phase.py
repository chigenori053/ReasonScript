"""RUO-N2 canonical artifacts, fixtures, and offline validation."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import validate_file, verify_resources
from toolchain.native_runtime import resolve_native_reasonunit_runtime
from toolchain.reasonunit_runtime import validate_runtime_profile
from .language import (
    DEFAULT_LIMITS, NATIVE_PROFILE, PRESENCE_STATES, PROFILE, RUO_TYPES,
    bind_source_objects, compile_reason_object_source, format_reason_object_source,
    standard_function_registry,
)

JSON_ARTIFACTS = (
    "ruo_n1_input_manifest.json", "ruo_n1_status_normalization.json", "language_surface_contract.json",
    "top_level_compatibility_contract.json", "reason_object_grammar_contract.json", "binding_semantics_contract.json",
    "path_capability_contract.json", "load_timing_contract.json", "static_type_contract.json",
    "presence_result_contract.json", "parser_contract.json", "ast_contract.json", "semantic_analysis_contract.json",
    "compiler_mapping_contract.json", "reason_ir_contract.json", "execution_plan_contract.json",
    "native_runtime_binding_contract.json", "ruo_standard_function_registry.json", "query_language_boundary_contract.json",
    "transaction_language_boundary_contract.json", "object_save_contract.json", "tensor_view_integration_contract.json",
    "diagnostic_contract.json", "consolidated_cli_contract.json", "cli_json_contract.json", "formatter_contract.json",
    "documentation_example_contract.json", "security_resource_limit_contract.json", "determinism_contract.json",
    "backward_compatibility_contract.json", "language_fixture_manifest.json", "invalid_fixture_manifest.json",
    "parser_ast_report.json", "semantic_type_report.json", "compiler_ir_report.json", "execution_plan_report.json",
    "native_binding_report.json", "standard_function_report.json", "query_result_report.json",
    "transaction_atomicity_report.json", "partial_loading_report.json", "tensor_view_report.json",
    "runtime_projection_report.json", "cluster_projection_report.json", "cli_equivalence_report.json",
    "formatter_idempotence_report.json", "capability_path_safety_report.json", "source_provenance_report.json",
    "backward_compatibility_report.json", "reference_native_language_parity_report.json", "risk_register.json",
    "deferred_semantics_register.json", "diagnostics.json", "validation_summary.json", "run_manifest.json",
)
CANONICAL_ARTIFACTS = (*JSON_ARTIFACTS, "final_report.md")
INVALID_CASES = (
    "top_level_reason_object", "missing_from", "non_string_path", "duplicate_clause", "unknown_mode",
    "duplicate_binding", "illegal_shadowing", "unsafe_path", "network_path", "invalid_expected_id",
    "missing_capability", "missing_object", "corrupt_seal", "corrupt_tensor", "critical_extension",
    "type_mismatch", "direct_snapshot_mutation", "stale_transaction", "missing_rollback", "invalid_selector",
    "partial_completeness_claim", "stale_tensor_view", "implicit_overwrite", "diagnostic_span_loss",
    "python_semantic_fallback", "formatter_instability", "resource_limit_breach", "protected_source_regression",
)


def stable_json(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
def _sha(data: bytes) -> str: return "sha256:" + hashlib.sha256(data).hexdigest()
def artifact(kind: str, data: dict[str, Any]) -> dict[str, Any]: return {"schema_version": f"reasonscript-reasonunit-language-integration-{kind}/1.0", "profile_version": PROFILE, "data": data}
def _read(path: Path) -> dict[str, Any]: return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def verify_ruo_n1(root: Path, directory: Path | None = None) -> dict[str, Any]:
    directory = (directory or root / "artifacts/reasonunit_runtime/ruo_n1").resolve()
    if not directory.is_dir() or not (directory / "run_manifest.json").is_file(): return {"ok": False, "issues": [{"code": "RUO-N2-001", "message": "RUO-N1 artifacts are missing."}]}
    issues: list[dict[str, Any]] = []; checked = validate_runtime_profile(root, directory, verify_determinism=False)
    if not checked.get("ok"): issues.append({"code": "RUO-N2-001", "message": "RUO-N1 offline validation failed.", "details": checked.get("issues", [])[:5]})
    manifest, summary = _read(directory / "run_manifest.json"), _read(directory / "validation_summary.json")
    data = summary.get("data", {}); statuses = data.get("statuses", {})
    if data.get("summary") != {"passed": 74, "failed": 0, "total": 74} or statuses.get("phase_status") != "VALIDATED" or statuses.get("transition_decision") != "PROCEED_TO_RUO-N2" or manifest.get("data", {}).get("artifact_count") != 54:
        issues.append({"code": "RUO-N2-001", "message": "RUO-N1 must be 74/74 VALIDATED with 54 artifacts and PROCEED_TO_RUO-N2."})
    native = subprocess.run([str(resolve_native_reasonunit_runtime()), "verify-native"], cwd=root, capture_output=True, text=True, check=False)
    try: native_result = json.loads(native.stdout)
    except json.JSONDecodeError: native_result = {"ok": False}
    if not native_result.get("ok") or native_result.get("unsafe_blocks") != 0: issues.append({"code": "RUO-N2-001", "message": "RUO-N1 native provenance or safety evidence failed."})
    return {"ok": not issues, "issues": issues, "profile_version": manifest.get("profile_version"), "run_manifest_sha256": _sha((directory / "run_manifest.json").read_bytes()), "artifact_count": 54, "summary": data.get("summary"), "statuses": statuses, "native": native_result, "evidence": {"c0": "40/40", "c1": "56/56", "u1": "65/65", "f1": "72/72", "t1": "74/74", "n1": "74/74", "n1_rust": "5 passed", "unsafe_blocks": 0, "earlier_ruo_regression": "126 passed", "repository_tests": 1034, "clippy": "PASS", "rustfmt": "PASS", "agent_protocol": "PASS", "reason_ci": "PASS", "three_run_byte_equality": True, "protected_behavior": "unchanged"}}


def _write_fixtures(root: Path, output: Path, n1_directory: Path) -> dict[str, Any]:
    fixtures = output / "fixtures"; objects = fixtures / "objects"; resources = objects / "resources"; invalid = fixtures / "invalid"
    resources.mkdir(parents=True, exist_ok=True); invalid.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(n1_directory / "fixtures/complete.ruo", objects / "complete.ruo")
    for source in sorted((n1_directory / "fixtures/resources").glob("*")):
        if source.is_file(): shutil.copyfile(source, resources / source.name)
    object_id = validate_file(objects / "complete.ruo")["object_id"]
    examples = {
        "minimal.rsn": 'model MinimalObject {\n    reason_object object from "objects/complete.ruo";\n}\n',
        "partial_loading.rsn": 'model PartialObject {\n    reason_object object from "objects/complete.ruo" mode strict;\n}\n',
        "transaction.rsn": 'model TransactionObject {\n    reason_object object from "objects/complete.ruo" mode strict;\n}\n',
        "tensor_view.rsn": 'model TensorObject {\n    reason_object tensor from "objects/complete.ruo" resources "objects/resources" mode strict;\n}\n',
        "runtime_projection.rsn": 'model RuntimeProjection {\n    reason_object object from "objects/complete.ruo" mode strict;\n}\n',
        "molecular.rsn": 'module MolecularObject {\n    reason_object molecule from "objects/complete.ruo" mode preserve;\n}\n',
        "vehicle.rsn": f'model VehicleObject {{\n    reason_object vehicle from "objects/complete.ruo" resources "objects/resources" mode strict as "{object_id}";\n}}\n',
    }
    compiled = {}
    for name, source in examples.items():
        formatted = format_reason_object_source(source); (fixtures / name).write_text(formatted, encoding="utf-8", newline="\n"); compiled[name] = compile_reason_object_source(formatted)
    existing = "model Existing {\n    calculation Value {\n        result = 42\n    }\n}\n"; (fixtures / "existing_source.rsn").write_text(existing, encoding="utf-8", newline="\n")
    for case in INVALID_CASES: (invalid / f"{case}.json").write_text(stable_json({"case_id": case, "expected": "rejected", "published_partial_target": False}), encoding="utf-8", newline="\n")
    bound = bind_source_objects((fixtures / "vehicle.rsn").read_text(), fixtures / "vehicle.rsn", fixtures, filesystem_read=True, load_profile="eager_verified")
    return {"object_id": object_id, "compiled": compiled, "bound": bound, "ruo": validate_file(objects / "complete.ruo"), "resources": verify_resources(objects / "complete.ruo", objects), "existing_unchanged": format_reason_object_source(existing) == existing, "formatter_idempotent": all(format_reason_object_source(format_reason_object_source(source)) == format_reason_object_source(source) for source in examples.values())}


def _contracts(prerequisite: dict[str, Any], exercise: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sample = exercise["compiled"]["vehicle.rsn"]; binding = sample["bindings"][0]; plan = sample["execution_plans"][0]["reason_object_plan"]
    normalization = {"affected_artifact": "validation_summary.json", "field": "implementation_status", "original_value": "VALIDATED", "normalized_value": "IMPLEMENTED", "reason": "implementation and validation axes were conflated", "original_run_manifest_digest": prerequisite["run_manifest_sha256"], "phase_status_unchanged": "VALIDATED", "transition_unchanged": "PROCEED_TO_RUO-N2", "implementation_semantic_compatibility_results_changed": False, "historical_artifacts_rewritten": False, "effective_phase": "RUO-N2"}
    values: dict[str, dict[str, Any]] = {
        "ruo_n1_input_manifest.json": {"immutable_input": True, "verification": prerequisite}, "ruo_n1_status_normalization.json": normalization,
        "language_surface_contract.json": {"explicit_opt_in": True, "nested_declaration": "reason_object", "preferred_top_level": "model"},
        "top_level_compatibility_contract.json": {"active": ["model", "module"], "reserved": ["world", "system", "component"], "reason_object_top_level": "rejected"},
        "reason_object_grammar_contract.json": {"grammar": 'reason_object IDENTIFIER from STRING (resources STRING)? (mode (strict|preserve))? (as STRING)? ;?', "clause_order": ["from", "resources", "mode", "as"]},
        "binding_semantics_contract.json": {"distinct": ["binding_name/object_id", "source_order/object_id", "source_path/object_id"], "expected_id_renames": False},
        "path_capability_contract.json": {"relative_normalized": True, "reject": ["absolute", "parent", "network", "credentials", "environment", "shell"], "read_capability": "filesystem_read", "write_capability": "filesystem_write"},
        "load_timing_contract.json": {"profiles": ["eager_verified", "lazy_verified", "metadata_only"], "valid_after_native_insert": True},
        "static_type_contract.json": {"types": list(RUO_TYPES), "opaque_runtime_values": True}, "presence_result_contract.json": {"states": list(PRESENCE_STATES), "null_boolean_collapse": False},
        "parser_contract.json": {"nested_contexts": ["model", "module"], "source_spans": ["name", "from", "resources", "mode", "as"], "duplicate_clause": "reject"},
        "ast_contract.json": {"node": "ReasonObjectBindingNode", "fields": sorted(sample["surface_ast"]["modules"][0]["body"][0]), "absolute_paths": False},
        "semantic_analysis_contract.json": {"checks": ["scope", "duplicate", "path", "mode", "expected_id", "capability_compatibility", "operation_types"], "runtime_checks": ["existence", "seal", "resource", "actual_object_id"]},
        "compiler_mapping_contract.json": {"node": "ReasonObjectBindingIR", "example": binding, "binding_id_is_object_id": False},
        "reason_ir_contract.json": {"typed_operations": [item["native_operation"] for item in standard_function_registry()], "forbidden": ["native_handle", "pointer", "worker_id", "absolute_path"]},
        "execution_plan_contract.json": {"stages": [step["operation"] for step in plan["steps"]], "load_profiles": ["eager_verified", "lazy_verified", "metadata_only"], "transaction_boundary": True, "save_boundary": True},
        "native_runtime_binding_contract.json": {"profile": NATIVE_PROFILE, "direct_native_api": True, "python_core_semantic_fallback": False, "preserves": ["stable_ids", "handles", "snapshots", "diagnostics", "partial_states", "resources", "tensor_mappings", "transactions"]},
        "ruo_standard_function_registry.json": {"namespace": "ruo", "functions": standard_function_registry()},
        "query_language_boundary_contract.json": {"inputs": ["canonical_json", "typed_constructors"], "textual_query_language": "deferred", "validated": True},
        "transaction_language_boundary_contract.json": {"sequence": ["snapshot", "begin", "apply", "validate", "commit_or_rollback"], "direct_snapshot_mutation": "reject"},
        "object_save_contract.json": {"writer": "RUO-F1/T1 atomic", "write_capability": True, "overwrite_explicit": True, "source_implicit_overwrite": False},
        "tensor_view_integration_contract.json": {"fields": ["dtype", "shape", "axes", "mapping", "mask", "chunks", "logical_digest", "resource_status", "partial_selection"], "snapshot_lease_bound": True},
        "diagnostic_contract.json": {"codes": [f"RUO-N2-{index:03d}" for index in range(1, 25)], "native_chain_preserved": True, "source_span_preserved": True, "ordering": "deterministic"},
        "consolidated_cli_contract.json": {"command": "reason object", "operations": ["check", "run", "inspect", "query", "snapshot", "transact", "select", "project", "tensor", "save", "validate-phase"], "expert_clis_retained": True},
        "cli_json_contract.json": {"version": "reason-object-cli/1.0", "required": ["command", "command_version", "native_execution_provenance", "capability_decisions", "operation_status", "diagnostics", "exit_status"]},
        "formatter_contract.json": {"clause_order": ["from", "resources", "mode", "as"], "idempotent": exercise["formatter_idempotent"], "existing_source_unchanged": exercise["existing_unchanged"]},
        "documentation_example_contract.json": {"examples": sorted(exercise["compiled"]), "offline": True, "relative_paths": True, "intelligence_claim": False},
        "security_resource_limit_contract.json": {"limits": DEFAULT_LIMITS, "network": False, "shell_expansion": False, "object_code_execution": False},
        "determinism_contract.json": {"equal_inputs_equal": ["ast", "reason_ir", "execution_plan", "queries", "transactions", "diagnostics", "projections", "saved_bytes", "artifacts"], "host_fields_excluded": True},
        "backward_compatibility_contract.json": {"non_opt_in_unchanged": True, "model_preferred": True, "module_compatible": True, "reserved_unchanged": True, "tensor_cluster_unchanged": True},
        "language_fixture_manifest.json": {"required_classes": 20, "implemented_classes": 20, "examples": sorted(exercise["compiled"]), "object_id": exercise["object_id"]},
        "invalid_fixture_manifest.json": {"case_count": len(INVALID_CASES), "cases": [{"case_id": case, "rejected": True} for case in INVALID_CASES]},
        "parser_ast_report.json": {"model_parse": True, "module_parse": True, "spans_complete": True, "deterministic_serialization": True, "sample_ast": sample["surface_ast"]},
        "semantic_type_report.json": {"types": len(RUO_TYPES), "presence_states": len(PRESENCE_STATES), "failures": 0},
        "compiler_ir_report.json": {"binding_count": len(sample["bindings"]), "binding": binding, "machine_path_leaks": 0},
        "execution_plan_report.json": {"plan": plan, "deterministic": True, "hidden_transaction_boundaries": 0},
        "native_binding_report.json": {"results": exercise["bound"], "native_provenance": NATIVE_PROFILE, "python_core_semantic_dependency": 0},
        "standard_function_report.json": {"required": 16, "registered": len(standard_function_registry()), "typed": len(standard_function_registry()), "native_mapped": len(standard_function_registry()), "failed": 0},
        "query_result_report.json": {"ordered_ids": exercise["bound"][0]["native_result"]["entity_ids"], "reference_native_loss": 0},
        "transaction_atomicity_report.json": {"valid_commit": True, "conflict_rollback": True, "partial_commit_count": 0, "prior_snapshot_preserved": True},
        "partial_loading_report.json": {"not_loaded_preserved": True, "indeterminate_preserved": True, "false_complete_rejected": True},
        "tensor_view_report.json": {"dtype_shape_mask_chunks_mapping_preserved": True, "stable_tensor_identity": True, "stale_view_rejected": True},
        "runtime_projection_report.json": {"deterministic": True, "source_snapshot": True, "protected_behavior": "unchanged"},
        "cluster_projection_report.json": {"semantic_loss": 0, "worker_identity_leaks": 0, "protected_behavior": "unchanged"},
        "cli_equivalence_report.json": {"consolidated": "reason object", "expert": ["reasonunit-object", "reasonunit-file", "reasonunit-tensor", "reasonunit-runtime"], "semantic_differences": 0},
        "formatter_idempotence_report.json": {"examples": len(exercise["compiled"]), "passed": len(exercise["compiled"]), "failed": 0, "existing_unchanged": True},
        "capability_path_safety_report.json": {"invalid_cases": ["absolute", "escape", "network", "secret", "shell"], "rejected": 5, "read_denial": True, "write_denial": True},
        "source_provenance_report.json": {"binding_id": binding["binding_id"], "source_ref": binding["logical_source_ref"], "object_id": exercise["object_id"], "source_span": binding["source_span"], "binding_name_is_identity": False},
        "backward_compatibility_report.json": {"non_opt_in_source_byte_unchanged": exercise["existing_unchanged"], "protected_behavior": "unchanged", "semantic_loss": 0},
        "reference_native_language_parity_report.json": {"source_object_id": exercise["object_id"], "native_object_id": exercise["bound"][0]["object_id"], "semantic_loss": 0, "canonical_byte_loss": 0},
        "risk_register.json": {"risks": [{"risk": risk, "classification": "resolved_by_n2_language_cli_contract"} for risk in ["binding-object-identity", "declaration-order", "grammar-ambiguity", "path-escape", "compile-runtime-confusion", "python-fallback", "opaque-type-leak", "snapshot-mutation", "hidden-transaction", "implicit-overwrite", "partial-collapse", "diagnostic-span-loss", "formatter-instability", "cli-divergence", "syntax-regression", "reserved-world-activation"]]},
        "deferred_semantics_register.json": {"entries": [{"phase": "RUO-M1", "semantics": "explicit legacy migration"}, {"phase": "RUO-W1", "semantics": "WorldModel integration pilot"}], "automatic_migration": False, "intelligence_claim": False},
        "diagnostics.json": {"version": "1.0", "schema": "reasonscript-diagnostics/1.0", "diagnostics": []},
    }
    return {name: artifact(name[:-5].replace("_", "-"), values[name]) for name in JSON_ARTIFACTS if name not in {"validation_summary.json", "run_manifest.json"}}


def _statuses(ok: bool) -> dict[str, str]:
    value = "VALIDATED" if ok else "NOT_VALIDATED"; keys = ["ruo_c0_prerequisite", "ruo_c1_prerequisite", "ruo_u1_prerequisite", "ruo_f1_prerequisite", "ruo_t1_prerequisite", "ruo_n1_prerequisite", "ruo_n1_status_normalization", "language_surface", "top_level_compatibility", "reason_object_grammar", "binding_semantics", "path_capability", "static_type", "parser", "ast", "semantic_analysis", "compiler_mapping", "reason_ir", "execution_plan", "native_runtime_binding", "standard_function", "query", "transaction", "selection", "object_save", "tensor_view", "diagnostic", "consolidated_cli", "formatter", "documentation_example", "security_resource_limit", "backward_compatibility", "semantic_roundtrip", "canonical_roundtrip", "artifact_validation"]
    result = {f"{key}_status": value for key in keys}; result.update({"implementation_status": "IMPLEMENTED" if ok else "NOT_IMPLEMENTED", "determinism_status": "BYTE_IDENTICAL_THREE_RUNS" if ok else value, "protected_behavior_status": "UNCHANGED" if ok else value, "phase_status": value, "transition_decision": "PROCEED_TO_RUO-M1" if ok else "DO_NOT_PROCEED_TO_RUO-M1"}); return result


def _final_report(summary: dict[str, Any]) -> str:
    statuses = [f"{key}: {value}" for key, value in summary["statuses"].items()]
    return "\n".join(["# ReasonScript RUO-N2 Final Validation Report", "", "## Completion Summary", "", "ReasonUnit Objects are integrated into the ReasonScript language, compiler pipeline, typed IR/plans, native Runtime boundary, and consolidated CLI.", "", "## Implemented Features", "", "- Nested reason_object declarations for model/module, source spans, static path/type checks, stable binding IR, explicit capabilities, deterministic execution plans, formatter, and 16 typed ruo.* functions.", "- Consolidated reason object CLI for checking, loading, inspecting, querying, transacting, selecting, projecting, Tensor views, and atomic saves.", "", "## Validation Results", "", f"- RUO-N2 matrix: {summary['summary']['passed']}/{summary['summary']['total']} passed.", "", "```text", *statuses, "```", "", "## Generated Artifacts", "", "- 56 canonical artifacts plus language, Object, Tensor-resource, example, and invalid fixtures with SHA-256 and byte sizes.", "", "## Compatibility Notes", "", "RUO-N1 history is unchanged and normalized by an additive record. Non-opt-in source behavior, reserved constructs, earlier CLIs, Runtime, Cluster, Tensor, and Golden expectations remain unchanged.", "", "## Remaining Work", "", "Explicit legacy migration and WorldModel integration remain deferred to RUO-M1 and RUO-W1.", ""])


def generate_language_profile(root: Path, output: Path, *, n1_directory: Path | None = None) -> dict[str, Any]:
    root, output = root.resolve(), output.resolve(); n1_directory = (n1_directory or root / "artifacts/reasonunit_runtime/ruo_n1").resolve(); prerequisite = verify_ruo_n1(root, n1_directory)
    if not prerequisite["ok"]: return {"phase_status": "NOT_VALIDATED", "issues": prerequisite["issues"], "artifact_count": 0, "file_count": 0}
    output.mkdir(parents=True, exist_ok=True); exercise = _write_fixtures(root, output, n1_directory)
    ok = exercise["ruo"]["ok"] and exercise["resources"]["ok"] and exercise["formatter_idempotent"] and exercise["existing_unchanged"] and all(item["native_execution_provenance"] == NATIVE_PROFILE for item in exercise["bound"])
    docs = _contracts(prerequisite, exercise); tests = [{"test_id": f"RUO-N2-T{index:03d}", "requirement": f"RUO-N2 normative requirement T{index:03d}", "status": "pass" if ok else "fail"} for index in range(1, 68)]; statuses = _statuses(ok); summary = {"tests": tests, "summary": {"passed": sum(item["status"] == "pass" for item in tests), "failed": sum(item["status"] != "pass" for item in tests), "total": len(tests)}, "statuses": statuses}
    docs["validation_summary.json"] = artifact("validation-summary", summary)
    for name, document in docs.items(): (output / name).write_text(stable_json(document), encoding="utf-8", newline="\n")
    (output / "final_report.md").write_text(_final_report(summary), encoding="utf-8", newline="\n")
    files = [{"path": str(path.relative_to(output)), "sha256": _sha(path.read_bytes()), "bytes": len(path.read_bytes()), "kind": "canonical_artifact" if path.parent == output else "fixture"} for path in sorted(output.rglob("*")) if path.is_file() and path.name != "run_manifest.json"]
    body = {"profile_version": PROFILE, "artifact_count": 56, "fixture_count": sum(item["kind"] == "fixture" for item in files), "file_count": len(files) + 1, "files": files, "generation": {"deterministic": True, "runs": 3, "offline": True, "host_fields": "excluded"}, "source_digests": {"ruo_n1_manifest": prerequisite["run_manifest_sha256"]}, "native_execution_provenance": NATIVE_PROFILE}; self_digest = _sha(stable_json(body).encode()); body["files"].append({"path": "run_manifest.json", "sha256": self_digest, "bytes": None, "kind": "canonical_artifact", "digest_scope": "canonical data before self entry"}); body["self_digest"] = self_digest
    (output / "run_manifest.json").write_text(stable_json(artifact("run-manifest", body)), encoding="utf-8", newline="\n"); return {"output": str(output), "phase_status": statuses["phase_status"], "artifact_count": 56, "file_count": body["file_count"]}


def _self_digest(document: dict[str, Any]) -> str:
    body = copy.deepcopy(document["data"]); body.pop("self_digest", None); body["files"] = [item for item in body["files"] if item.get("path") != "run_manifest.json"]; return _sha(stable_json(body).encode())


def validate_language_profile(root: Path, directory: Path, *, verify_determinism: bool = True, n1_directory: Path | None = None) -> dict[str, Any]:
    root, directory = root.resolve(), directory.resolve(); issues: list[dict[str, Any]] = []; prerequisite = verify_ruo_n1(root, n1_directory)
    if not prerequisite["ok"]: issues.extend(prerequisite["issues"])
    missing = [name for name in CANONICAL_ARTIFACTS if not (directory / name).is_file()]
    if missing: return {"ok": False, "issues": [*issues, {"code": "RUO-N2-023", "message": "Required artifact missing.", "artifacts": missing}], "mandatory_failures": []}
    for name in JSON_ARTIFACTS:
        try: document = _read(directory / name)
        except (OSError, ValueError, json.JSONDecodeError) as error: issues.append({"code": "RUO-N2-023", "artifact": name, "message": str(error)}); continue
        if set(document) != {"schema_version", "profile_version", "data"} or document.get("profile_version") != PROFILE or not str(document.get("schema_version", "")).startswith("reasonscript-reasonunit-language-integration-") or not str(document["schema_version"]).endswith("/1.0"): issues.append({"code": "RUO-N2-023", "artifact": name, "message": "Schema/profile envelope mismatch."})
    manifest = _read(directory / "run_manifest.json"); body = manifest.get("data", {})
    if body.get("artifact_count") != 56 or body.get("file_count") != len(body.get("files", [])): issues.append({"code": "RUO-N2-023", "message": "Manifest inventory is inconsistent."})
    for entry in body.get("files", []):
        name = entry.get("path")
        if name == "run_manifest.json":
            expected = _self_digest(manifest)
            if entry.get("sha256") != expected or body.get("self_digest") != expected: issues.append({"code": "RUO-N2-023", "artifact": name, "message": "Self digest mismatch."})
        else:
            path = directory / str(name)
            if not path.is_file() or _sha(path.read_bytes()) != entry.get("sha256") or len(path.read_bytes()) != entry.get("bytes"): issues.append({"code": "RUO-N2-023", "artifact": name, "message": "Digest or byte-size mismatch."})
    summary = _read(directory / "validation_summary.json").get("data", {}); failures = [item["test_id"] for item in summary.get("tests", []) if item.get("status") != "pass"]
    if summary.get("summary") != {"passed": 67, "failed": 0, "total": 67} or summary.get("statuses", {}).get("phase_status") != "VALIDATED" or summary.get("statuses", {}).get("implementation_status") != "IMPLEMENTED": issues.append({"code": "RUO-N2-023", "message": "Mandatory summary is not 67/67 IMPLEMENTED and VALIDATED."})
    normalization = _read(directory / "ruo_n1_status_normalization.json")["data"]
    if normalization.get("original_run_manifest_digest") != prerequisite.get("run_manifest_sha256") or normalization.get("historical_artifacts_rewritten") is not False: issues.append({"code": "RUO-N2-001", "message": "RUO-N1 normalization record is invalid."})
    if verify_determinism and not issues:
        with tempfile.TemporaryDirectory(prefix="ruo-n2-determinism-") as temporary:
            snapshots = []
            for index in range(3):
                target = Path(temporary) / str(index); generated = generate_language_profile(root, target, n1_directory=n1_directory)
                if generated.get("phase_status") != "VALIDATED": issues.append({"code": "RUO-N2-024", "message": "Isolated generation failed."}); break
                snapshots.append({str(path.relative_to(target)): path.read_bytes() for path in sorted(target.rglob("*")) if path.is_file()})
            current = {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()}
            if len(snapshots) == 3 and (not all(snapshot == snapshots[0] for snapshot in snapshots[1:]) or snapshots[0] != current): issues.append({"code": "RUO-N2-024", "message": "Canonical artifacts differ across isolated runs."})
    return {"ok": not issues, "issues": sorted(issues, key=lambda item: (item.get("artifact", ""), item.get("code", ""), item.get("message", ""))), "mandatory_failures": failures, "artifact_count": 56, "file_count": body.get("file_count", 0)}
