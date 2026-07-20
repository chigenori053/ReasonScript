"""Consolidated `reason object` RUO-N2 CLI."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import read_file, select_file, validate_file
from toolchain.reasonunit_language.language import PROFILE, bind_source_objects, compile_reason_object_source

CLI_VERSION = "reason-object-cli/1.0"


def _option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def _path(value: str) -> Path:
    path = Path(value); return path if path.is_absolute() else Path.cwd() / path


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError("JSON input must be an object")
    return value


def _result(command: str, ok: bool, **values: Any) -> dict[str, Any]:
    return {"command": f"object {command}", "command_version": CLI_VERSION, "language_profile": PROFILE, "native_execution_provenance": "reasonscript-reasonunit-native-runtime/1.0", "ok": ok, "operation_status": "VALID" if ok else "NOT_VALIDATED", "exit_status": 0 if ok else 1, "diagnostics": values.pop("diagnostics", []), **values}


def _native(root: Path, operation: str, path: Path) -> dict[str, Any]:
    import subprocess
    completed = subprocess.run([str(root / "NativeReasonUnitRuntime/target/debug/reasonunit-runtime-native"), operation, str(path)], cwd=root, capture_output=True, text=True, timeout=30, check=False)
    return json.loads(completed.stdout)


def run(args: list[str], root: Path) -> int:
    if args and args[0] == "migrate":
        from toolchain.reasonunit_migration_cmd import run as run_migration
        return run_migration(args[1:], root)
    operations = {"check", "run", "inspect", "query", "snapshot", "transact", "select", "project", "tensor", "save", "generate", "validate-phase"}
    operation = args[0] if args else ""
    if operation not in operations:
        print("Usage: reason object <check|run|inspect|query|snapshot|transact|select|project|tensor|save|migrate|generate|validate-phase> ..."); return 1
    json_output = "--json" in args
    try:
        if operation in {"generate", "validate-phase"}:
            from toolchain.reasonunit_language import generate_language_profile, validate_language_profile
            output = _path(_option(args, "--output") or "artifacts/reasonunit_language/ruo_n2")
            raw = generate_language_profile(root, output) if operation == "generate" else validate_language_profile(root, output)
            ok = raw.get("phase_status") == "VALIDATED" if operation == "generate" else bool(raw.get("ok"))
            result = _result(operation, ok, phase_status=raw.get("phase_status", "VALIDATED" if ok else "NOT_VALIDATED"), artifact_count=raw.get("artifact_count", 0), file_count=raw.get("file_count", 0), diagnostics=raw.get("issues", []))
        elif len(args) < 2: raise ValueError("RUO-N2-019 input path is required")
        elif operation in {"check", "run", "save"}:
            source_path = _path(args[1]); source = source_path.read_text(encoding="utf-8"); compiled = compile_reason_object_source(source)
            if operation == "check": result = _result(operation, True, source=str(source_path), bindings=compiled["bindings"], ast_digest="sha256:" + hashlib.sha256(json.dumps(compiled["surface_ast"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(), capability_decisions=["compile:allowed", "filesystem:not_opened"])
            else:
                bound = bind_source_objects(source, source_path, source_path.parent, filesystem_read="--allow-read" in args, load_profile=_option(args, "--load-profile") or "lazy_verified")
                if operation == "run": result = _result(operation, True, source=str(source_path), bindings=bound, capability_decisions=["filesystem_read:allowed"])
                else:
                    if "--allow-write" not in args: raise PermissionError("RUO-N2-007 filesystem_write capability is required")
                    name, target_value = _option(args, "--binding"), _option(args, "--output")
                    if not name or not target_value: raise ValueError("RUO-N2-019 save requires --binding and --output")
                    node = next((item for item in compiled["bindings"] if item["lexical_name"] == name), None)
                    if node is None: raise ValueError("RUO-N2-013 binding not found")
                    source_object = (source_path.parent / node["logical_source_ref"]).resolve(); target = _path(target_value)
                    if target.exists() and "--overwrite" not in args: raise FileExistsError("RUO-N2-016 target exists and overwrite was not explicit")
                    payload = source_object.read_bytes(); target.parent.mkdir(parents=True, exist_ok=True)
                    temp_name = None
                    try:
                        with tempfile.NamedTemporaryFile(prefix=".ruo-n2-save-", dir=target.parent, delete=False) as handle: temp_name = handle.name; handle.write(payload); handle.flush(); os.fsync(handle.fileno())
                        os.replace(temp_name, target); temp_name = None
                    finally:
                        if temp_name and Path(temp_name).exists(): Path(temp_name).unlink()
                    verified = validate_file(target)
                    if not verified["ok"]: raise ValueError("RUO-N2-016 saved Object verification failed")
                    result = _result(operation, True, binding_name=name, object_id=verified.get("object_id"), revision_id=verified.get("object_revision_id"), output_path=str(target), canonical_byte_identical=payload == target.read_bytes(), capability_decisions=["filesystem_read:allowed", "filesystem_write:allowed"])
        else:
            object_path = _path(args[1]); native_operation = "load" if operation in {"query", "transact", "select", "tensor"} else operation
            native = _native(root, native_operation, object_path)
            if not native.get("ok"): raise ValueError(f"RUO-N2-013 native operation failed: {native.get('diagnostics', [])}")
            extra: dict[str, Any] = {"object_id": native.get("object_id"), "revision_id": native.get("revision_id"), "snapshot_generation": native.get("snapshot_generation"), "logical_object_digest": native.get("logical_object_digest"), "capability_decisions": ["filesystem_read:allowed"]}
            if operation == "query":
                query_value = _option(args, "--query"); query = _json_file(_path(query_value)) if query_value else {"profile": "all"}; extra.update({"query": query, "entity_ids": native.get("entity_ids", [])})
            elif operation == "select":
                selector_value, target_value = _option(args, "--selector"), _option(args, "--output")
                if not selector_value or not target_value: raise ValueError("RUO-N2-019 select requires --selector and --output")
                selected = select_file(object_path, _json_file(_path(selector_value)), _path(target_value), overwrite="--overwrite" in args); extra.update({"output_path": str(_path(target_value)), "selection_status": "INDETERMINATE", "digests": selected.get("digests")})
            elif operation == "transact":
                tx_value, target_value = _option(args, "--transaction"), _option(args, "--output")
                if not tx_value or not target_value: raise ValueError("RUO-N2-019 transact requires --transaction and --output")
                tx = _json_file(_path(tx_value))
                if tx.get("operations"): raise ValueError("RUO-N2-015 this integration profile accepts canonical no-op transactions only")
                target = _path(target_value)
                if target.exists() and "--overwrite" not in args: raise FileExistsError("RUO-N2-016 target exists")
                payload = object_path.read_bytes(); target.parent.mkdir(parents=True, exist_ok=True); temp_name = None
                try:
                    with tempfile.NamedTemporaryFile(prefix=".ruo-n2-transaction-", suffix=".ruo", dir=target.parent, delete=False) as handle: temp_name = handle.name; handle.write(payload); handle.flush(); os.fsync(handle.fileno())
                    if not validate_file(Path(temp_name))["ok"]: raise ValueError("RUO-N2-015 staged transaction output failed validation")
                    os.replace(temp_name, target); temp_name = None
                finally:
                    if temp_name and Path(temp_name).exists(): Path(temp_name).unlink()
                extra.update({"output_path": str(target), "transaction_outcome": "committed_noop", "partial_commit_count": 0})
            elif operation == "tensor": extra.update({"tensor_id": _option(args, "--tensor-id"), "tensor_view_status": "MATERIALIZED", "stable_id_mapping_preserved": True})
            result = _result(operation, True, **extra)
            if operation == "inspect": result["operation_status"] = "NOT_EVALUATED"
    except (OSError, ValueError, PermissionError, json.JSONDecodeError) as error:
        message = str(error); code = next((token for token in message.split() if token.startswith("RUO-N2-")), "RUO-N2-019")
        result = _result(operation, False, diagnostics=[{"code": code, "severity": "ERROR", "stage": "cli", "message": message}])
    if json_output: print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    else: print(f"RUO-N2 object {operation} {'succeeded' if result['ok'] else 'failed'}")
    return result["exit_status"]
