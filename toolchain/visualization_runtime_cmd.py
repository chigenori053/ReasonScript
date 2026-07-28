"""Thin CLI adapter for the safe-Rust Semantic Visualization Runtime."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


PROFILE = "reasonscript-semantic-visualization-runtime/0.1"
REQUIRED_ARTIFACTS = (
    "visualization_manifest.json",
    "visualization_source.json",
    "visualization_scene.json",
    "visualization_render_plan.json",
    "visualization_evidence.json",
    "visualization_trace.json",
    "visualization_validation.json",
    "visualization_run_summary.json",
    "scene.svg",
)


def _option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def _invoke(args: list[str]) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    crate = root / "VisualizationRuntime"
    binary_name = "reason-visualization.exe" if os.name == "nt" else "reason-visualization"
    binary = crate / "target" / "debug" / binary_name
    sources = [crate / "Cargo.toml", *(crate / "src").glob("*.rs")]
    current = binary.is_file() and binary.stat().st_mtime_ns >= max(path.stat().st_mtime_ns for path in sources)
    command = [str(binary), *args] if current else [
        "cargo", "run", "--offline", "--quiet", "--manifest-path", str(crate / "Cargo.toml"),
        "--bin", "reason-visualization", "--", *args,
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "exit_status": 1, "profile": PROFILE,
                "diagnostics": [{"code": "SVR-CLI-004", "severity": "error", "message": completed.stderr or "native output was not JSON", "location": "adapter"}]}


def _validate_phase(directory: Path) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    try:
        root = directory.resolve()
        documents: dict[str, Any] = {}
        for name in REQUIRED_ARTIFACTS:
            path = root / name
            if not path.is_file():
                diagnostics.append({"code": "SVR-ART-001", "severity": "error", "message": f"Missing artifact: {name}", "location": name})
            elif path.suffix == ".json":
                documents[name] = json.loads(path.read_text(encoding="utf-8"))
        manifest = documents.get("visualization_manifest.json", {})
        if manifest.get("schema_version") != "reasonscript-semantic-visualization-manifest/0.1" or manifest.get("profile") != PROFILE:
            diagnostics.append({"code": "SVR-ART-001", "severity": "error", "message": "Invalid visualization manifest profile", "location": "visualization_manifest.json"})
        entries = {entry.get("path"): entry for entry in manifest.get("artifacts", []) if isinstance(entry, dict)}
        for name in REQUIRED_ARTIFACTS[1:]:
            data = (root / name).read_bytes() if (root / name).is_file() else b""
            entry = entries.get(name, {})
            if entry.get("sha256") != "sha256:" + hashlib.sha256(data).hexdigest() or entry.get("bytes") != len(data):
                diagnostics.append({"code": "SVR-ART-001", "severity": "error", "message": f"Artifact digest mismatch: {name}", "location": name})
        scene = documents.get("visualization_scene.json", {})
        if scene.get("schema_version") != "reasonscript-semantic-visualization-ir/0.1":
            diagnostics.append({"code": "SVR-ART-001", "severity": "error", "message": "Invalid semantic visualization scene schema", "location": "visualization_scene.json"})
        if documents.get("visualization_validation.json", {}).get("status") != "pass":
            diagnostics.append({"code": "SVR-ART-001", "severity": "error", "message": "Visualization validation status is not pass", "location": "visualization_validation.json"})
    except (OSError, ValueError, json.JSONDecodeError) as error:
        diagnostics.append({"code": "SVR-ART-001", "severity": "error", "message": str(error), "location": "artifact"})
    diagnostics.sort(key=lambda item: (item["code"], item.get("location", ""), item["message"]))
    return {"ok": not diagnostics, "exit_status": 0 if not diagnostics else 1, "profile": PROFILE,
            "operation": "validate-phase", "phase_status": "VALIDATED" if not diagnostics else "NOT_VALIDATED", "diagnostics": diagnostics}


def run(args: list[str], root: Path) -> int:
    operation = args[0] if args else ""
    json_output = "--json" in args
    if operation not in {"project", "project-vision", "validate", "verify-native", "generate", "validate-phase"}:
        print("Usage: reason visualization <project|project-vision|validate|verify-native|generate|validate-phase> ...")
        return 1
    if operation == "generate":
        output = _path(_option(args, "--output") or "artifacts/semantic_visualization_runtime/v0_1")
        fixture = Path(__file__).resolve().parents[1] / "canonical_fixtures/visualization_runtime/person_structure.json"
        result = _invoke(["project", str(fixture), "--output", str(output)])
        if result.get("ok"):
            result = _validate_phase(output)
            result["operation"] = "generate"
            result["output"] = str(output)
    elif operation == "validate-phase":
        result = _validate_phase(_path(_option(args, "--output") or "artifacts/semantic_visualization_runtime/v0_1"))
    elif operation == "verify-native":
        result = _invoke([operation])
    else:
        positional = next((item for item in args[1:] if not item.startswith("--") and item != _option(args, "--output")), None)
        if positional is None:
            result = {"ok": False, "exit_status": 1, "profile": PROFILE, "diagnostics": [{"code": "SVR-CLI-003", "severity": "error", "message": "input path is required", "location": "cli"}]}
        else:
            native = [operation, str(_path(positional))]
            output = _option(args, "--output")
            if output:
                native.extend(["--output", str(_path(output))])
            result = _invoke(native)
    if json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    else:
        print(f"Semantic Visualization Runtime {operation} {'succeeded' if result.get('ok') else 'failed'}")
    return int(result.get("exit_status", 1))
