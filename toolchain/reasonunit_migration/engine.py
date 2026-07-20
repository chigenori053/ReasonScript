"""Deterministic, staged, zero-loss migration of legacy ReasonUnit JSON."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import read_file, validate_file, write_file
from toolchain.reasonunit_object.model import canonical_digest, validate_object
from toolchain.reasonunit_object.universal import reference_object
from toolchain.reasonunit_language import bind_source_objects
from toolchain.reasonunit_tensor import PAYLOAD_PROFILE, TensorError, make_dense_tensor, tensor_resource_record, validate_tensor

PROFILE = "reasonscript-reasonunit-migration/1.0"
MAX_SOURCE_FILES = 10_000
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_UNITS = 10_000


class MigrationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code} {message}"); self.code = code


def _stable(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else _stable(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (OSError, ValueError, json.JSONDecodeError) as error: raise MigrationError("RUO-M1-004", f"invalid JSON input: {error}") from error
    if not isinstance(value, dict): raise MigrationError("RUO-M1-004", "input must be a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".ruo-m1-", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name); handle.write(_stable(value)); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path); temporary = None
    finally:
        if temporary and temporary.exists(): temporary.unlink()


def _inside(path: Path, root: Path) -> bool:
    try: path.relative_to(root); return True
    except ValueError: return False


def discover(source: Path, output: Path) -> dict[str, Any]:
    if source.is_symlink(): raise MigrationError("RUO-M1-021", "symlink source rejected")
    source = source.resolve()
    if not source.exists(): raise MigrationError("RUO-M1-002", "source does not exist")
    if source.is_dir() and _inside(output.resolve(), source): raise MigrationError("RUO-M1-021", "inventory output must be outside the immutable source root")
    base = source if source.is_dir() else source.parent
    candidates = [source] if source.is_file() else sorted(source.rglob("*.json"))
    if len(candidates) > MAX_SOURCE_FILES: raise MigrationError("RUO-M1-021", "source file-count limit exceeded")
    entries = []
    for path in candidates:
        if path.is_symlink() or not _inside(path.resolve(), base): raise MigrationError("RUO-M1-021", "symlink or root escape rejected")
        payload = path.read_bytes()
        if len(payload) > MAX_SOURCE_BYTES: raise MigrationError("RUO-M1-021", "source byte limit exceeded")
        relative = path.name if source.is_file() else path.relative_to(source).as_posix()
        classification = "project_local" if isinstance(_load(path).get("units"), list) else "documentation_only"
        entries.append({"relative_path": relative, "sha256": _digest(payload), "bytes": len(payload), "classification": classification})
    result = {"profile_version": PROFILE, "source_root": str(source), "source_kind": "directory" if source.is_dir() else "file", "entries": entries, "inventory_digest": _digest(entries), "read_only": True, "network_access": False}
    _write_json(output, result); return result


def analyze(inventory_path: Path, profile: str) -> dict[str, Any]:
    inventory = _load(inventory_path); supported = [e for e in inventory.get("entries", []) if e.get("classification") in {"reasonscript_native_legacy", "runtime_native_legacy", "cluster_native_legacy", "tensor_native_legacy", "standard_schema_legacy", "project_local", "adapter_owned"}]
    if not supported: raise MigrationError("RUO-M1-003", "no supported semantic authority")
    return {"profile_version": PROFILE, "inventory": str(inventory_path.resolve()), "inventory_digest": inventory.get("inventory_digest"), "mapping_profile": profile, "units": supported, "authorities": {"legacy_source": "identity_and_semantics", "mapping_profile": "target_representation", "extensions": "opaque_lossless"}, "analysis_digest": _digest([inventory.get("inventory_digest"), profile, supported])}


def _identity(namespace: str, project: str, locator: str, kind: str) -> str:
    token = hashlib.sha256(_stable([namespace, project, locator, kind])).hexdigest()[:24]
    return f"ruo:{namespace}:{token}"


def plan(analysis_path: Path, output: Path) -> dict[str, Any]:
    analysis = _load(analysis_path); inventory_path = Path(str(analysis["inventory"])); inventory = _load(inventory_path)
    source_root = Path(str(inventory["source_root"])); units = []
    for entry in analysis.get("units", []):
        source = source_root if inventory.get("source_kind") == "file" else source_root / entry["relative_path"]
        legacy = _load(source); project = str(legacy.get("project_id") or "default")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,127}", project) is None: raise MigrationError("RUO-M1-004", "logical project ID is not a safe canonical name")
        if len(legacy.get("units", [])) > MAX_UNITS: raise MigrationError("RUO-M1-021", "entity limit exceeded")
        object_id = str(legacy.get("object_id") or _identity("object", project, "object", "reasonunit_object"))
        mappings = []
        for index, unit in enumerate(legacy.get("units", [])):
            if not isinstance(unit, dict): raise MigrationError("RUO-M1-004", "legacy unit must be an object")
            locator = str(unit.get("locator") or unit.get("name") or f"unit-{index}"); kind = str(unit.get("kind") or "atomic_reasonunit")
            target_id = str(unit.get("id") or _identity("unit", project, locator, kind))
            mappings.append({"legacy_locator": locator, "legacy_id": unit.get("id"), "semantic_locator": locator, "kind": kind, "target_kind": "composite_reasonunit" if kind in {"composite", "composite_reasonunit"} or unit.get("children") else "atomic_reasonunit", "target_id": target_id, "preservation_status": "preserved" if unit.get("id") else "generated", "source_digest": entry["sha256"], "mapping_rationale": "explicit stable ID" if unit.get("id") else "versioned semantic-locator policy", "aliases": [], "replacement_history": [], "ambiguity_status": "resolved", "generation_inputs": None if unit.get("id") else {"policy": "ruo-m1-semantic-id/1", "project_id": project, "semantic_locator": locator, "kind": kind, "namespace": "unit"}})
        target_ids = [item["target_id"] for item in mappings]
        if len(target_ids) != len(set(target_ids)): raise MigrationError("RUO-M1-005", "legacy identity collision")
        units.append({"source": str(source), "source_sha256": entry["sha256"], "project_id": project, "object_id": object_id, "identity_mappings": mappings})
    project_ids = [item["project_id"] for item in units]; object_ids = [item["object_id"] for item in units]
    if len(project_ids) != len(set(project_ids)) or len(object_ids) != len(set(object_ids)): raise MigrationError("RUO-M1-005", "migration-unit project or Object identity collision")
    body = {"profile_version": PROFILE, "migration_id": _identity("object", "migration", analysis["analysis_digest"], "migration"), "analysis_digest": analysis["analysis_digest"], "mapping_profile": analysis["mapping_profile"], "migration_units": units, "resource_root_policy": "staging-relative-only", "expected_consumers": ["reason_object binding"], "publication_policy": "explicit atomic project batch", "rollback_policy": "restore previous directory and retain evidence", "limits": {"source_files": MAX_SOURCE_FILES, "source_bytes": MAX_SOURCE_BYTES, "units": MAX_UNITS}, "capabilities": {"network": False, "source_write": False, "publication_write": "explicit"}, "batch_atomic": True, "acceptance_mode": "zero_loss_or_approved_extension", "plan_digest": ""}
    body["plan_digest"] = _digest({k: v for k, v in body.items() if k != "plan_digest"}); _write_json(output, body); return body


def _check_plan(value: dict[str, Any]) -> None:
    expected = _digest({k: v for k, v in value.items() if k != "plan_digest"})
    if value.get("plan_digest") != expected: raise MigrationError("RUO-M1-015", "plan digest mismatch")
    for unit in value.get("migration_units", []):
        if _digest(Path(unit["source"]).read_bytes()) != unit["source_sha256"]: raise MigrationError("RUO-M1-015", "source changed after discovery freeze")


def dry_run(plan_path: Path, staging: Path) -> dict[str, Any]:
    value = _load(plan_path); _check_plan(value)
    actions = [{"source": u["source"], "output": f"objects/{u['project_id']}.ruo", "mapping_count": len(u["identity_mappings"])} for u in value["migration_units"]]
    conversion = convert(plan_path, staging); validation = validate(plan_path, staging)
    result = {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "staging": str(staging.resolve()), "actions": actions, "writes_outside_staging": 0, "staged_output_count": len(conversion["records"]), "validation": validation["status"], "status": "DRY_RUN_VALID"}
    _write_json(staging / "dry_run_report.json", result); return result


def _convert_one(spec: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    legacy = _load(Path(spec["source"])); target = reference_object(); revision = "ruo:revision:migration-0"; object_id = spec["object_id"]
    target["object_identity"].update({"entity_id": object_id, "created_revision": revision, "last_modified_revision": revision})
    target["current_revision"] = revision; target["revisions"] = [{"revision_id": revision, "transaction_id": "ruo:transaction:migration", "source_revision": None, "changed_entities": []}]
    mappings = spec["identity_mappings"]; id_by_locator = {m["semantic_locator"]: m["target_id"] for m in mappings}
    base = {"schema_version": "1.0", "created_revision": revision, "last_modified_revision": revision, "lifecycle_state": "active", "extensions": {}}
    target["units"] = []
    for raw, mapping in zip(legacy["units"], mappings):
        children = [id_by_locator.get(str(child), str(child)) for child in raw.get("children", [])]
        kind = "composite_reasonunit" if children or mapping["kind"] in {"composite", "composite_reasonunit"} else "atomic_reasonunit"
        target["units"].append({**base, "entity_id": mapping["target_id"], "entity_kind": kind, "owner_object_id": object_id, "children": children, "extensions": {"legacy": raw}})
    children = {child for unit in target["units"] for child in unit["children"]}; target["root_units"] = [u["entity_id"] for u in target["units"] if u["entity_id"] not in children]
    target["payloads"] = []; target["states"] = []; target["relations"] = []; target["constraints"] = []; target["evidence_registry"] = []; target["dependency_graph"] = []; target["projection_descriptors"] = []; target["external_resources"] = []; resources: list[tuple[str, bytes]] = []
    tensor = legacy.get("tensor")
    if isinstance(tensor, dict) and all(key in tensor for key in ("dtype", "shape", "values")):
        tensor_id = _identity("payload", spec["project_id"], "tensor", "tensor")
        locator = f"resources/{spec['project_id']}.ruot"
        try: body, payload = make_dense_tensor(str(tensor["dtype"]), list(tensor["shape"]), list(tensor["values"]), tensor_id=tensor_id, locator=locator)
        except (TensorError, TypeError, ValueError) as error: raise MigrationError("RUO-M1-012", f"legacy Tensor cannot be represented losslessly: {error}") from error
        if not validate_tensor(body, resource_bytes=payload)["ok"]: raise MigrationError("RUO-M1-012", "legacy Tensor cannot be represented losslessly")
        target["payloads"].append({"payload_id": tensor_id, "profile_id": PAYLOAD_PROFILE, "profile_version": "1", "owner_id": object_id, "semantic_role": "ruo.role:tensor", "value_presence": "present", "value": body, "constraints": [], "provenance_refs": [], "extensions": {"legacy": tensor}})
        target["external_resources"].append(tensor_resource_record(body)); resources.append((locator, payload))
    target["extension_registry"] = [{"namespace": "legacy", "authority": "source", "version": "1", "entity_kinds": ["object", "unit"], "canonical_ordering": "key", "compatibility": "retain", "opaque_retention": True}]
    target["extensions"] = {"legacy": {k: v for k, v in legacy.items() if k != "units"}, "migration": {"profile": PROFILE, "source_sha256": spec["source_sha256"]}}
    diagnostics = validate_object(target)
    if diagnostics: raise MigrationError("RUO-M1-006", f"converted object invalid: {diagnostics[0]['message']}")
    return target, resources


def convert(plan_path: Path, staging: Path) -> dict[str, Any]:
    value = _load(plan_path); _check_plan(value); staging.mkdir(parents=True, exist_ok=True); objects = staging / "objects"; build = Path(tempfile.mkdtemp(prefix=".objects-build-", dir=staging)); records = []
    try:
        for spec in value["migration_units"]:
            target = build / f"{spec['project_id']}.ruo"; converted, resources = _convert_one(spec)
            for locator, payload in resources:
                resource_path = build / locator; resource_path.parent.mkdir(parents=True, exist_ok=True); resource_path.write_bytes(payload)
            written = write_file(converted, target, overwrite=True)
            records.append({"project_id": spec["project_id"], "path": str(objects / target.name), "object_id": spec["object_id"], "logical_digest": canonical_digest(converted), "file_digest": _digest(target.read_bytes()), "source_sha256": spec["source_sha256"], "identity_mappings": spec["identity_mappings"], "writer": written})
        previous = staging / ".objects-previous"
        if previous.exists(): shutil.rmtree(previous)
        if objects.exists(): os.replace(objects, previous)
        try: os.replace(build, objects); build = Path("")
        except Exception:
            if previous.exists(): os.replace(previous, objects)
            raise
        if previous.exists(): shutil.rmtree(previous)
    finally:
        if build and build.exists() and build != Path("."): shutil.rmtree(build)
    result = {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "records": records, "partial_commit_count": 0, "status": "STAGED"}; _write_json(staging / "conversion_report.json", result); return result


def compare(plan_path: Path, staging: Path) -> dict[str, Any]:
    value = _load(plan_path); _check_plan(value); losses = []
    for spec in value["migration_units"]:
        target = read_file(staging / "objects" / f"{spec['project_id']}.ruo"); legacy = _load(Path(spec["source"])); retained = target.get("extensions", {}).get("legacy", {})
        units_by_id = {u.get("entity_id"): u for u in target["units"]}
        reconstructed = {**retained, "units": [units_by_id[m["target_id"]].get("extensions", {}).get("legacy") for m in spec["identity_mappings"]]}
        if reconstructed != legacy: losses.append(spec["project_id"])
    result = {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "semantic_loss_count": len(losses), "loss_projects": losses, "acceptance": "ACCEPTED" if not losses else "REJECTED"}; _write_json(staging / "semantic_comparison_report.json", result)
    if losses: raise MigrationError("RUO-M1-016", "semantic comparison detected loss")
    return result


def validate(plan_path: Path, staging: Path) -> dict[str, Any]:
    value = _load(plan_path); _check_plan(value); results = []
    for spec in value["migration_units"]:
        path = staging / "objects" / f"{spec['project_id']}.ruo"; check = validate_file(path); logical = read_file(path)
        tensor_checks = []
        for payload in logical.get("payloads", []):
            if payload.get("profile_id") == PAYLOAD_PROFILE:
                body = payload["value"]; resource = (path.parent / body["storage"]["locator"]).read_bytes(); tensor_checks.append(validate_tensor(body, resource_bytes=resource))
        native = subprocess.run([str(Path(__file__).resolve().parents[2] / "NativeReasonUnitRuntime/target/debug/reasonunit-runtime-native"), "load", str(path)], capture_output=True, text=True, timeout=30, check=False)
        try: native_result = json.loads(native.stdout)
        except json.JSONDecodeError: native_result = {"ok": False}
        binding_source = f'model MigrationValidation {{\n reason_object migrated from "objects/{spec["project_id"]}.ruo" mode strict as "{spec["object_id"]}";\n}}\n'
        try: bindings = bind_source_objects(binding_source, staging / "migration_validation.rsn", staging, filesystem_read=True, load_profile="eager_verified"); n2_ok = len(bindings) == 1
        except (OSError, ValueError, PermissionError): bindings = []; n2_ok = False
        ok = bool(check.get("ok")) and all(item.get("ok") for item in tensor_checks) and bool(native_result.get("ok")) and n2_ok
        results.append({"project_id": spec["project_id"], "ok": ok, "u1_f1": check.get("ok", False), "t1": all(item.get("ok") for item in tensor_checks), "n1": native_result.get("ok", False), "n2": n2_ok})
    comparison = compare(plan_path, staging); ok = all(r["ok"] for r in results) and comparison["semantic_loss_count"] == 0
    result = {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "results": results, "semantic_loss_count": comparison["semantic_loss_count"], "status": "VALIDATED" if ok else "NOT_VALIDATED"}; _write_json(staging / "validation_report.json", result)
    if not ok: raise MigrationError("RUO-M1-015", "staged migration validation failed")
    return result


def publish(plan_path: Path, staging: Path, target: Path, *, allow_write: bool) -> dict[str, Any]:
    if not allow_write: raise MigrationError("RUO-M1-021", "publication requires --allow-write")
    value = _load(plan_path); validation = validate(plan_path, staging); target = target.resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    active = target / "active_migration.json"
    if active.is_file() and _load(active).get("plan_digest") == value["plan_digest"]:
        return {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "target": str(target), "validation": validation["status"], "status": "ALREADY_PUBLISHED", "partial_commit_count": 0, "rollback": str(target / "rollback.json")}
    previous = target.parent / f".{target.name}.previous"; temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.publish-", dir=target.parent))
    try:
        shutil.copytree(staging / "objects", temporary / "objects"); shutil.copytree(staging, temporary / "migration_evidence"); shutil.copy2(plan_path, temporary / "migration_plan.json")
        bindings = [f' reason_object {u["project_id"].replace("-", "_")} from "objects/{u["project_id"]}.ruo" mode strict as "{u["object_id"]}";' for u in value["migration_units"]]
        (temporary / "consumer_binding.rsn").write_text("model MigratedObjects {\n" + "\n".join(bindings) + "\n}\n", encoding="utf-8", newline="\n")
        _write_json(temporary / "active_migration.json", {"plan_digest": value["plan_digest"], "status": "active", "consumer_binding": "consumer_binding.rsn"})
        if target.exists():
            if previous.exists(): shutil.rmtree(previous)
            os.replace(target, previous)
        os.replace(temporary, target)
    except Exception:
        if not target.exists() and previous.exists(): os.replace(previous, target)
        shutil.rmtree(temporary, ignore_errors=True); raise
    rollback_doc = {"profile_version": PROFILE, "target": str(target), "previous": str(previous), "plan_digest": value["plan_digest"], "published": True}
    _write_json(target / "rollback.json", rollback_doc)
    return {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "target": str(target), "validation": validation["status"], "status": "PUBLISHED", "partial_commit_count": 0, "rollback": str(target / "rollback.json")}


def rollback(rollback_path: Path, *, allow_write: bool) -> dict[str, Any]:
    if not allow_write: raise MigrationError("RUO-M1-021", "rollback requires --allow-write")
    value = _load(rollback_path); target, previous = Path(value["target"]), Path(value["previous"]); archived = target.parent / f".{target.name}.rolled-back"
    if not target.exists(): raise MigrationError("RUO-M1-019", "published target is missing")
    if archived.exists(): shutil.rmtree(archived)
    os.replace(target, archived)
    if previous.exists(): os.replace(previous, target)
    return {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "status": "ROLLED_BACK", "published_evidence": str(archived), "legacy_preserved": True}


def status(plan_path: Path, staging: Path | None = None) -> dict[str, Any]:
    value = _load(plan_path); _check_plan(value); reports = {}
    if staging:
        for name in ("dry_run_report.json", "conversion_report.json", "semantic_comparison_report.json", "validation_report.json"):
            reports[name] = (staging / name).is_file()
    return {"profile_version": PROFILE, "plan_digest": value["plan_digest"], "source_frozen": True, "reports": reports, "status": "VALIDATED" if reports.get("validation_report.json") else "PLANNED"}
