"""CLI adapter for the RUO-T1 Tensor representation profile."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from toolchain.reasonunit_file import read_file, write_file
from toolchain.reasonunit_tensor import (
    MEDIA_TYPE,
    PAYLOAD_PROFILE,
    PROFILE,
    TensorError,
    convert_tensor,
    dense_values,
    encode_values,
    logical_digest,
    make_dense_tensor,
    select_tensor,
    validate_tensor,
    verify_resource,
)


def _option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def _path(value: str) -> Path:
    path = Path(value); return path if path.is_absolute() else Path.cwd() / path


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    if not isinstance(value, dict): raise ValueError("JSON input must be an object")
    return value


def _result(command: str, ok: bool, **data: Any) -> dict[str, Any]:
    return {"command": command, "diagnostics": data.pop("diagnostics", []), "exit_status": 0 if ok else 1, "tensor_profile": PROFILE, "ok": ok, **data}


def _tensors(logical: dict[str, Any], tensor_id: str | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    found = []
    for payload in logical.get("payloads", []):
        if payload.get("profile_id") == PAYLOAD_PROFILE and (tensor_id is None or payload.get("payload_id") == tensor_id):
        body = payload.get("value", payload.get("body"))
            if isinstance(body, dict): found.append((payload, body))
    return found


def _resource_root(args: list[str], object_path: Path) -> Path:
    value = _option(args, "--resource-root"); return _path(value) if value else object_path.parent


def run(args: list[str], root: Path) -> int:
    operations = {"encode", "validate", "inspect", "decode", "select", "convert", "verify-resources", "generate", "validate-phase"}
    if not args or args[0] not in operations:
        print("Usage: reason reasonunit-tensor <encode|validate|inspect|decode|select|convert|verify-resources|generate|validate-phase> ..."); return 1
    operation, json_output = args[0], "--json" in args
    try:
        if operation in {"generate", "validate-phase"}:
            from toolchain.reasonunit_tensor import (
                generate_tensor_profile,
                validate_tensor_profile,
            )
            output = _path(_option(args, "--output") or "artifacts/reasonunit_tensor/ruo_t1")
            f1_value = _option(args, "--ruo-f1"); f1 = _path(f1_value) if f1_value else None
            raw = generate_tensor_profile(root, output, f1_directory=f1) if operation == "generate" else validate_tensor_profile(root, output, f1_directory=f1)
            ok = raw.get("phase_status") == "VALIDATED" if operation == "generate" else bool(raw.get("ok"))
            result = _result(operation, ok, artifact_count=raw.get("artifact_count", 0), file_count=raw.get("file_count", 0), phase_status=raw.get("phase_status", "VALIDATED" if ok else "NOT_VALIDATED"), diagnostics=raw.get("issues", []))
        elif len(args) < 2: raise TensorError("RUO-T1-002", "Input path is required.", stage="cli")
        elif operation == "encode":
            source = _json(_path(args[1])); target_value = _option(args, "--output")
            if not target_value: raise TensorError("RUO-T1-011", "encode requires --output TENSOR.ruot", stage="cli")
            if "tensor_profile" in source:
                body = source; values = source.get("values", source.get("storage", {}).get("values"))
                if body.get("representation") == "inline": values = dense_values(body)
            else: body = {}; values = source.get("values")
            if not isinstance(values, list): raise TensorError("RUO-T1-010", "encode input requires flattened values.", stage="cli")
            dtype, shape = source.get("dtype"), source.get("shape"); data = encode_values(dtype, values)
            target = _path(target_value)
            if target.suffix != ".ruot": raise TensorError("RUO-T1-011", "Tensor Resource extension must be .ruot.", stage="cli")
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
            result = _result(operation, True, tensor_id=source.get("payload_id"), resource_id=source.get("resource_id"), dtype=dtype, shape=shape, representation="dense_resource", selected_ranges=[], mapping_status="NOT_EVALUATED", integrity_status="VALID", semantic_status="VALID", resource_sha256="sha256:" + hashlib.sha256(data).hexdigest(), byte_size=len(data))
        else:
            object_path = _path(args[1]); logical = read_file(object_path); tensor_id = _option(args, "--tensor-id"); tensors = _tensors(logical, tensor_id)
            if not tensors: raise TensorError("RUO-T1-002", "Requested Tensor Payload was not found.", stage="cli", tensor_id=tensor_id)
            root_path = _resource_root(args, object_path)
            if operation == "inspect":
                details = [{"tensor_id": body.get("payload_id", payload.get("payload_id")), "dtype": body.get("dtype"), "shape": body.get("shape"), "representation": body.get("representation"), "logical_digest": body.get("logical_digest"), "resource_id": body.get("storage", {}).get("resource_id"), "selected_ranges": body.get("selection", {}).get("slice_ranges", []), "mapping_status": "NOT_EVALUATED", "integrity_status": "NOT_EVALUATED", "semantic_status": "NOT_EVALUATED"} for payload, body in tensors]
                result = _result(operation, True, tensors=details, tensor_id=details[0]["tensor_id"] if len(details) == 1 else None, dtype=details[0]["dtype"] if len(details) == 1 else None, shape=details[0]["shape"] if len(details) == 1 else None, representation=details[0]["representation"] if len(details) == 1 else None, selected_ranges=[], mapping_status="NOT_EVALUATED", integrity_status="NOT_EVALUATED", semantic_status="NOT_EVALUATED")
            elif operation in {"validate", "verify-resources"}:
                validations = [verify_resource(body, root_path) if body.get("representation") == "dense_resource" else validate_tensor(body) for _, body in tensors]
                ok = all(item["ok"] for item in validations); first = validations[0]
                result = _result(operation, ok, tensors=validations, tensor_id=first.get("tensor_id"), dtype=first.get("dtype"), shape=first.get("shape"), representation=first.get("representation"), selected_ranges=[], mapping_status=first.get("mapping_status"), integrity_status=first.get("integrity_status"), semantic_status=first.get("semantic_status"), diagnostics=[diagnostic for item in validations for diagnostic in item.get("diagnostics", [])])
            else:
                payload, body = tensors[0]; resource = None
                if body.get("representation") == "dense_resource":
                    from toolchain.reasonunit_tensor import resolve_resource
                    resource = resolve_resource(body, root_path)
                if operation == "decode":
                    target_value = _option(args, "--output")
                    if not target_value: raise TensorError("RUO-T1-002", "decode requires --output OUTPUT_JSON", stage="cli")
                    values = dense_values(body, resource_bytes=resource); output = {"tensor_id": payload["payload_id"], "dtype": body["dtype"], "shape": body["shape"], "values": values}
                    _path(target_value).write_text(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
                    result = _result(operation, True, tensor_id=payload["payload_id"], dtype=body["dtype"], shape=body["shape"], representation=body["representation"], selected_ranges=[], mapping_status="VALID", integrity_status="VALID", semantic_status="VALID")
                elif operation == "select":
                    selector_value, target_value = _option(args, "--selector"), _option(args, "--output")
                    if not selector_value or not target_value: raise TensorError("RUO-T1-016", "select requires --selector SELECTOR_JSON and --output PARTIAL.ruo", stage="cli")
                    selected = select_tensor(body, _json(_path(selector_value)), resource_bytes=resource); selected["payload_id"] = payload["payload_id"]; selected["logical_digest"] = logical_digest(selected)
                    candidate = copy.deepcopy(logical); target_payload = next(item for item in candidate["payloads"] if item["payload_id"] == payload["payload_id"]); target_payload["value"] = selected; target_payload["value_presence"] = "present"
                    candidate["external_resources"] = [item for item in candidate.get("external_resources", []) if item.get("owner_payload_id") != payload["payload_id"]]
                    write_file(candidate, _path(target_value), overwrite="--overwrite" in args)
                    result = _result(operation, True, tensor_id=payload["payload_id"], dtype=selected["dtype"], shape=selected["shape"], representation="inline", selected_ranges=selected["selection"]["slice_ranges"], mapping_status="VALID", integrity_status="VALID", semantic_status="INDETERMINATE")
                else:
                    target_representation = _option(args, "--representation")
                    if not target_representation: raise TensorError("RUO-T1-019", "convert requires --representation TARGET", stage="cli")
                    converted = convert_tensor(body, target_representation, resource_bytes=resource); target_value = _option(args, "--output")
                    if target_value: _path(target_value).write_text(json.dumps(converted, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
                    result = _result(operation, True, tensor_id=payload["payload_id"], dtype=converted["dtype"], shape=converted["shape"], representation=converted["representation"], selected_ranges=[], mapping_status="VALID", integrity_status="VALID", semantic_status="VALID", conversion=converted["conversion"])
    except (OSError, ValueError, json.JSONDecodeError) as error:
        diagnostic = error.diagnostic() if isinstance(error, TensorError) else TensorError("RUO-T1-002", str(error), stage="cli").diagnostic()
        result = _result(operation, False, selected_ranges=[], mapping_status="NOT_VALIDATED", integrity_status="NOT_VALIDATED", semantic_status="NOT_VALIDATED", diagnostics=[diagnostic])
    if json_output: print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    else: print(f"RUO-T1 {operation} {'succeeded' if result['ok'] else 'failed'}")
    return result["exit_status"]
