"""CLI adapter for RUO-F1 file operations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import (
    FORMAT_VERSION,
    RUOFileError,
    inspect_file,
    read_file,
    select_file,
    validate_file,
    verify_resources,
    write_file,
)


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    if not isinstance(value, dict): raise ValueError("JSON input must be an object")
    return value


def _option(args: list[str], name: str) -> str | None:
    if name not in args or args.index(name) + 1 >= len(args): return None
    return args[args.index(name) + 1]


def _path(value: str) -> Path:
    path = Path(value); return path if path.is_absolute() else Path.cwd() / path


def _result(command: str, ok: bool, **data: Any) -> dict[str, Any]:
    return {"command": command, "diagnostics": data.pop("diagnostics", []), "exit_status": 0 if ok else 1, "format_version": FORMAT_VERSION, "ok": ok, **data}


def run(args: list[str], root: Path) -> int:
    operations = {"write", "validate", "inspect", "read", "select", "verify-resources", "generate", "validate-phase"}
    if not args or args[0] not in operations:
        print("Usage: reason reasonunit-file <write|validate|inspect|read|select|verify-resources|generate|validate-phase> ..."); return 1
    operation = args[0]; json_output = "--json" in args
    try:
        if operation in {"generate", "validate-phase"}:
            from toolchain.reasonunit_file import (
                generate_file_format,
                validate_file_format,
            )
            output = _path(_option(args, "--output") or "artifacts/reasonunit_file/ruo_f1")
            u1_value = _option(args, "--ruo-u1"); u1 = _path(u1_value) if u1_value else None
            raw = generate_file_format(root, output, u1_directory=u1) if operation == "generate" else validate_file_format(root, output, u1_directory=u1)
            ok = raw.get("phase_status") == "VALIDATED" if operation == "generate" else bool(raw.get("ok")); result = _result(operation, ok, artifact_count=raw.get("artifact_count", 0), file_count=raw.get("file_count", 0), phase_status=raw.get("phase_status", "VALIDATED" if ok else "NOT_VALIDATED"), diagnostics=raw.get("issues", []))
        elif len(args) < 2:
            raise RUOFileError("RUO-F1-002", "Input path is required.", stage="cli")
        elif operation == "write":
            source = _path(args[1]); target_value = _option(args, "--output")
            if not target_value: raise RUOFileError("RUO-F1-002", "write requires --output OBJECT.ruo", stage="cli")
            logical = _json_file(source); raw = write_file(logical, _path(target_value), overwrite="--overwrite" in args, expected_digest=_option(args, "--expected-digest")); result = _result(operation, True, input_identity=logical.get("object_identity", {}).get("entity_id"), output_identity=raw.get("object_id"), digest_results=raw.get("digests"), semantic_status=raw.get("semantic_status"), validation_stages=raw.get("validation_stages"))
        elif operation == "validate":
            raw = validate_file(_path(args[1]), mode=_option(args, "--mode") or "strict"); result = _result(operation, raw["ok"], input_identity=raw.get("object_id"), digest_results=raw.get("digests", {}), semantic_status=raw.get("semantic_status"), validation_stages=raw.get("validation_stages", {}), diagnostics=raw.get("diagnostics", []))
        elif operation == "inspect":
            raw = inspect_file(_path(args[1])); result = _result(operation, raw["ok"], input_identity=raw.get("object_id"), digest_results=raw.get("digests", {}), semantic_status="NOT_EVALUATED", validation_stages=raw.get("validation_stages", {}), diagnostics=raw.get("diagnostics", []))
        elif operation == "read":
            target_value = _option(args, "--output")
            if not target_value: raise RUOFileError("RUO-F1-002", "read requires --output OUTPUT.json", stage="cli")
            logical = read_file(_path(args[1]), mode=_option(args, "--mode") or "strict"); output = _path(target_value); output.parent.mkdir(parents=True, exist_ok=True); payload = json.dumps(logical, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"; output.write_text(payload, encoding="utf-8", newline="\n"); result = _result(operation, True, input_identity=logical["object_identity"]["entity_id"], output_identity=logical["object_identity"]["entity_id"], digest_results={"output_sha256": hashlib.sha256(payload.encode()).hexdigest()}, semantic_status="VALID", validation_stages={"read": "VALID"})
        elif operation == "select":
            selector_value = _option(args, "--selector"); target_value = _option(args, "--output")
            if not selector_value or not target_value: raise RUOFileError("RUO-F1-019", "select requires --selector SELECTOR.json and --output PARTIAL.ruo", stage="cli")
            selector = _json_file(_path(selector_value)); raw = select_file(_path(args[1]), selector, _path(target_value), overwrite="--overwrite" in args); result = _result(operation, True, input_identity=raw.get("object_id"), output_identity=raw.get("object_id"), digest_results=raw.get("digests"), semantic_status="INDETERMINATE", validation_stages=raw.get("validation_stages"))
        else:
            root_value = _option(args, "--resource-root")
            if not root_value: raise RUOFileError("RUO-F1-012", "verify-resources requires --resource-root ROOT", stage="cli")
            raw = verify_resources(_path(args[1]), _path(root_value)); result = _result(operation, raw["ok"], input_identity=read_file(_path(args[1]))["object_identity"]["entity_id"], digest_results={}, semantic_status="VALID", validation_stages={"external_resource_status": raw["external_resource_status"]}, diagnostics=[] if raw["ok"] else raw["results"])
    except (OSError, ValueError, json.JSONDecodeError) as error:
        diagnostic = error.diagnostic() if isinstance(error, RUOFileError) else {"code": "RUO-F1-004", "severity": "ERROR", "stage": "cli", "message": str(error)}; result = _result(operation, False, semantic_status="NOT_VALIDATED", validation_stages={}, diagnostics=[diagnostic])
    if json_output: print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else: print(f"RUO-F1 {operation} {'succeeded' if result['ok'] else 'failed'}")
    return result["exit_status"]
