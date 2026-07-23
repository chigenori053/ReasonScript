"""Thin CLI boundary for the RUO-N1 native Runtime."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from toolchain.native_runtime import resolve_native_reasonunit_runtime
from toolchain.reasonunit_runtime import PROFILE, generate_runtime_profile, validate_runtime_profile


def _option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def _path(value: str) -> Path:
    path = Path(value); return path if path.is_absolute() else Path.cwd() / path


def run(args: list[str], root: Path) -> int:
    operations = {"load", "validate", "inspect", "query", "snapshot", "transact", "select", "project", "verify-native", "generate", "validate-phase"}
    operation = args[0] if args else ""
    if operation not in operations:
        print("Usage: reason reasonunit-runtime <load|validate|inspect|query|snapshot|transact|select|project|verify-native|generate|validate-phase> ..."); return 1
    json_output = "--json" in args
    if operation in {"generate", "validate-phase"}:
        output = _path(_option(args, "--output") or "artifacts/reasonunit_runtime/ruo_n1")
        t1_value = _option(args, "--ruo-t1"); t1 = _path(t1_value) if t1_value else None
        raw = generate_runtime_profile(root, output, t1_directory=t1) if operation == "generate" else validate_runtime_profile(root, output, t1_directory=t1)
        ok = raw.get("phase_status") == "VALIDATED" if operation == "generate" else bool(raw.get("ok"))
        result = {"ok": ok, "exit_status": 0 if ok else 1, "operation": operation, "native_execution_provenance": PROFILE, "phase_status": raw.get("phase_status", "VALIDATED" if ok else "NOT_VALIDATED"), "artifact_count": raw.get("artifact_count", 0), "file_count": raw.get("file_count", 0), "diagnostics": raw.get("issues", [])}
    else:
        binary = resolve_native_reasonunit_runtime(root)
        native_args = [str(binary), operation]
        if operation != "verify-native":
            if len(args) < 2: print("OBJECT.ruo is required"); return 1
            native_args.append(str(_path(args[1])))
        completed = subprocess.run(native_args, cwd=root, capture_output=True, text=True, check=False)
        try: result = json.loads(completed.stdout)
        except json.JSONDecodeError: result = {"ok": False, "exit_status": 1, "operation": operation, "native_execution_provenance": PROFILE, "diagnostics": [{"code": "RUO-N1-021", "message": completed.stderr or "native adapter output invalid"}]}
    if json_output: print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    else: print(f"RUO-N1 {operation} {'succeeded' if result.get('ok') else 'failed'}")
    return int(result.get("exit_status", 1))
