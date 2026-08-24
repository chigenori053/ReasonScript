"""Thin CLI adapter for the safe-Rust Vision Runtime."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from toolchain.reasonunit_object.model import validate_object
from toolchain.reasonunit_tensor import validate_tensor

PROFILE = "reasonscript-vision-runtime/0.1"
LANGUAGE_PROFILE = "reasonscript-vision-language-integration/0.1"


def _option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def _invoke(root: Path, args: list[str]) -> dict[str, Any]:
    distribution_root = Path(__file__).resolve().parents[1]
    crate = distribution_root / "ReasonRuntime/crates/vision-core"
    workspace_target = distribution_root / "ReasonRuntime" / "target"
    binary_name = "reason-vision.exe" if os.name == "nt" else "reason-vision"
    installed_binary = distribution_root / "bin" / binary_name
    release_binary = workspace_target / "release" / binary_name
    debug_binary = workspace_target / "debug" / binary_name
    binary = installed_binary if installed_binary.is_file() else (release_binary if release_binary.is_file() else debug_binary)
    sources = [crate / "Cargo.toml", *(crate / "src").glob("*.rs")]
    binary_current = installed_binary.is_file() or (binary.is_file() and binary.stat().st_mtime_ns >= max(path.stat().st_mtime_ns for path in sources))
    command = [str(binary), *args] if binary_current else [
        "cargo", "run", "--offline", "--quiet", "--manifest-path", str(crate / "Cargo.toml"),
        "--bin", "reason-vision", "--", *args,
    ]
    completed = subprocess.run(command, cwd=distribution_root, capture_output=True, text=True, check=False)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result = {
            "ok": False, "exit_status": 1, "profile": PROFILE,
            "diagnostics": [{"code": "VIS-CLI-004", "stage": "adapter", "message": completed.stderr or "native output was not JSON"}],
        }
    return result


def _validate_phase(directory: Path) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    object_path = directory / "vision_object.json"
    manifest_path = directory / "vision_manifest.json"
    language_path = directory / "vision_language_profile.json"
    try:
        object_value = json.loads(object_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        language = json.loads(language_path.read_text(encoding="utf-8"))
        diagnostics.extend(validate_object(object_value))
        observed_object_digest = "sha256:" + hashlib.sha256(object_path.read_bytes()).hexdigest()
        if manifest.get("profile") != PROFILE or manifest.get("object_sha256") != observed_object_digest:
            diagnostics.append({"code": "VIS-ART-001", "stage": "manifest", "message": "Vision manifest identity or Object digest mismatch."})
        if language.get("profile") != LANGUAGE_PROFILE or [entry.get("qualified_name") for entry in language.get("functions", [])] != ["vision.infer", "vision.build_ruo"]:
            diagnostics.append({"code": "VIS-ART-004", "stage": "language", "message": "Vision language integration profile mismatch."})
        resources = {entry.get("path"): entry for entry in manifest.get("resources", []) if isinstance(entry, dict)}
        for payload in object_value.get("payloads", []):
            if payload.get("profile_id") != "ruo.payload.tensor/1":
                continue
            body = payload.get("value", {})
            locator = body.get("storage", {}).get("locator")
            if not isinstance(locator, str) or not locator or "\\" in locator:
                raise ValueError("Unsafe Tensor resource locator")
            pure = PurePosixPath(locator)
            if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
                raise ValueError("Unsafe Tensor resource locator")
            resource_path = (directory / pure).resolve()
            resource_root = directory.resolve()
            if resource_root != resource_path and resource_root not in resource_path.parents:
                raise ValueError("Tensor resource escapes artifact root")
            data = resource_path.read_bytes()
            validation = validate_tensor(payload, resource_bytes=data)
            diagnostics.extend(validation.get("diagnostics", []))
            entry = resources.get(locator, {})
            if entry.get("sha256") != "sha256:" + hashlib.sha256(data).hexdigest() or entry.get("byte_size") != len(data):
                diagnostics.append({"code": "VIS-ART-002", "stage": "resource", "message": f"Resource manifest mismatch: {locator}"})
    except (OSError, ValueError, json.JSONDecodeError) as error:
        diagnostics.append({"code": "VIS-ART-003", "stage": "artifact", "message": str(error)})
    diagnostics.sort(key=lambda item: (str(item.get("code", "")), str(item.get("stage", "")), str(item.get("message", ""))))
    return {
        "ok": not diagnostics,
        "exit_status": 0 if not diagnostics else 1,
        "profile": PROFILE,
        "operation": "validate-phase",
        "phase_status": "VALIDATED" if not diagnostics else "NOT_VALIDATED",
        "diagnostics": diagnostics,
    }


def _write_language_profile(directory: Path) -> None:
    from frontend.vision.contracts import VISION_TYPES, public_registry

    value = {
        "schema_version": "reasonscript-vision-language-profile/0.1",
        "profile": LANGUAGE_PROFILE,
        "types": list(VISION_TYPES),
        "functions": list(public_registry()),
        "lowering": ["vision_infer", "vision_build_ruo"],
        "publication_policy": "atomic_ruo_f1",
    }
    (directory / "vision_language_profile.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run(args: list[str], root: Path) -> int:
    operations = {"infer", "validate-observation", "build-ruo", "verify-native", "generate", "validate-phase"}
    operation = args[0] if args else ""
    json_output = "--json" in args
    if operation not in operations:
        print("Usage: reason vision <infer|validate-observation|build-ruo|verify-native|generate|validate-phase> ...")
        return 1
    if operation == "generate":
        output = _path(_option(args, "--output") or "artifacts/vision_runtime/v0_1")
        fixture = Path(__file__).resolve().parents[1] / "canonical_fixtures/vision_runtime/solar_observation.json"
        result = _invoke(root, ["build-ruo", str(fixture), "--output", str(output)])
        if result.get("ok"):
            _write_language_profile(output)
            result = _validate_phase(output)
            result["operation"] = "generate"
            result["output"] = str(output)
    elif operation == "validate-phase":
        output = _path(_option(args, "--output") or "artifacts/vision_runtime/v0_1")
        result = _validate_phase(output)
    elif operation == "infer":
        positional = [item for item in args[1:] if not item.startswith("--")]
        result = _invoke(root, ["infer", str(_path(positional[0])), str(_path(positional[1]))]) if len(positional) >= 2 else {"ok": False, "exit_status": 1, "profile": PROFILE, "diagnostics": [{"code": "VIS-CLI-003", "stage": "cli", "message": "model and image paths are required"}]}
    else:
        native_args = [operation]
        if operation != "verify-native":
            positional = next((item for item in args[1:] if not item.startswith("--") and item != _option(args, "--output")), None)
            if positional is None:
                result = {"ok": False, "exit_status": 1, "profile": PROFILE, "diagnostics": [{"code": "VIS-CLI-003", "stage": "cli", "message": "input path is required"}]}
            else:
                native_args.append(str(_path(positional)))
                output = _option(args, "--output")
                if output:
                    native_args.extend(["--output", str(_path(output))])
                result = _invoke(root, native_args)
        else:
            result = _invoke(root, native_args)
    if json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    else:
        print(f"Vision Runtime {operation} {'succeeded' if result.get('ok') else 'failed'}")
    return int(result.get("exit_status", 1))
